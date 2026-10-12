import csv
import hashlib
import io
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import PurePosixPath

MAX_FILES = 2000
MAX_TOTAL_SIZE = 500 * 1024 * 1024
MAX_FILE_SIZE = 100 * 1024 * 1024
MAX_RATIO = 200

CATEGORIES = {
    'PDFs': {'.pdf'},
    'Imagens': {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'},
    'Planilhas': {'.xlsx', '.xls', '.csv', '.ods'},
    'Documentos': {'.docx', '.doc', '.txt', '.rtf', '.odt'},
    'Apresentacoes': {'.pptx', '.ppt', '.odp'},
    'Videos': {'.mp4', '.mov', '.avi', '.mkv'},
    'Audios': {'.mp3', '.wav', '.ogg', '.flac'},
    'Compactados': {'.zip', '.rar', '.7z'},
}


def category_for(filename):
    suffix = PurePosixPath(filename).suffix.lower()
    return next((cat for cat, extensions in CATEGORIES.items() if suffix in extensions), 'Outros')


def week_for(date):
    monday = date - timedelta(days=date.weekday())
    sunday = monday + timedelta(days=6)
    return f'{monday.year}/Semana_{monday:%d-%m}_a_{sunday:%d-%m}'


def safe_name(name):
    result = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip(' .')
    return result or 'arquivo'


def folder_for(record, critical_ids):
    if record['id'] in critical_ids:
        return '01_Arquivos_Criticos'
    if record['duplicado']:
        return '03_Duplicados_Para_Revisao'
    year, week_name = record['semana'].split('/', 1)
    return f'02_{week_name}-{year}'


def analyze_zip(uploaded_bytes):
    records = []
    contents = {}
    total_size = 0
    try:
        archive = zipfile.ZipFile(io.BytesIO(uploaded_bytes))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError('O arquivo enviado não é um ZIP válido.') from exc

    with archive:
        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
        if len(entries) > MAX_FILES:
            raise ValueError(f'O ZIP excede o limite de {MAX_FILES} arquivos.')

        for index, entry in enumerate(entries):
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename
                    or entry.filename.startswith('/') or ':' in entry.filename):
                raise ValueError('O ZIP contém um caminho inseguro.')
            file_type = (entry.external_attr >> 16) & 0o170000
            if file_type == 0o120000:
                raise ValueError('Links simbólicos não são permitidos.')
            if file_type not in (0, 0o100000):
                raise ValueError('O ZIP contém um tipo de arquivo não permitido.')
            if entry.flag_bits & 0x1:
                raise ValueError('ZIPs com arquivos criptografados não são suportados.')
            if entry.file_size > MAX_FILE_SIZE:
                raise ValueError('O ZIP contém um arquivo acima de 100 MB.')
            total_size += entry.file_size
            if total_size > MAX_TOTAL_SIZE:
                raise ValueError('O ZIP excede 500 MB descompactados.')
            if entry.file_size > 1024 * 1024 and entry.file_size / max(entry.compress_size, 1) > MAX_RATIO:
                raise ValueError('O ZIP contém compressão suspeita.')
            try:
                with archive.open(entry) as source:
                    data = source.read(MAX_FILE_SIZE + 1)
            except (RuntimeError, zipfile.BadZipFile, OSError) as exc:
                raise ValueError('Não foi possível ler um arquivo do ZIP.') from exc
            if len(data) != entry.file_size:
                raise ValueError('Não foi possível ler o arquivo integralmente.')
            try:
                modified = datetime(*entry.date_time)
            except (ValueError, TypeError):
                modified = datetime(1980, 1, 1)
            name = safe_name(path.name)
            file_id = str(index)
            records.append({
                'id': file_id, 'nome': name, 'origem': entry.filename,
                'tipo': category_for(name), 'semana': week_for(modified),
                'tamanho': len(data), 'hash': hashlib.sha256(data).hexdigest(),
                'duplicado': False, 'critico': False,
            })
            contents[file_id] = data

    groups = defaultdict(list)
    for record in records:
        groups[record['hash']].append(record)
    for group in groups.values():
        if len(group) > 1:
            for record in group:
                record['duplicado'] = True
    return records, contents


def export_zip(records, contents, critical_ids, included_ids=None):
    """Exporta apenas IDs incluídos; relatório registra também os excluídos.

    O ZIP original e o conteúdo em memória nunca são modificados.
    """
    all_ids = {record['id'] for record in records}
    critical_ids = set(critical_ids) & all_ids
    included_ids = all_ids if included_ids is None else set(included_ids) & all_ids
    output = io.BytesIO()
    report = io.StringIO(newline='')
    writer = csv.writer(report, delimiter=';')
    writer.writerow([
        'Nome', 'Origem', 'Tipo', 'Semana', 'Tamanho (bytes)',
        'Duplicado', 'Critico', 'Incluido no ZIP', 'Motivo da exclusao',
        'Destino previsto ou exportado', 'SHA256',
    ])
    used_paths = set()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for record in records:
            file_id = record['id']
            critical = file_id in critical_ids
            included = file_id in included_ids
            folder = folder_for(record, critical_ids)
            name = record['nome']
            path = PurePosixPath(name)
            destination = f'{folder}/{name}'
            counter = 2
            if included:
                while destination.casefold() in used_paths:
                    destination = f'{folder}/{path.stem}_{counter}{path.suffix}'
                    counter += 1
                used_paths.add(destination.casefold())
                archive.writestr(destination, contents[file_id])
            writer.writerow([
                name, record['origem'], record['tipo'], record['semana'],
                record['tamanho'], 'Sim' if record['duplicado'] else 'Nao',
                'Sim' if critical else 'Nao', 'Sim' if included else 'Nao',
                '' if included else 'Desmarcado pelo usuario na conferencia',
                destination if included else f'{folder}/{name} (nao exportado)',
                record['hash'],
            ])
        archive.writestr('Relatorio_Geral.csv', '\ufeff' + report.getvalue())
    return output.getvalue()


def summary(records):
    return {
        'total': len(records),
        'duplicados': sum(bool(record['duplicado']) for record in records),
        'semanas': len({record['semana'] for record in records}),
        'tipos': dict(Counter(record['tipo'] for record in records)),
    }
