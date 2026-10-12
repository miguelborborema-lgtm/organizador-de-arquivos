import hashlib
from collections import defaultdict

import pandas as pd
import streamlit as st

from core.organizer import analyze_zip, export_zip, folder_for, summary

st.set_page_config(page_title='Organizador de Arquivos', page_icon='📁', layout='wide')


from pathlib import Path

def carregar_estilo():
    caminho_css = Path(__file__).resolve().parent / "styles" / "app.css"

    if caminho_css.is_file():
        css = caminho_css.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

carregar_estilo()

def pretty_size(size):
    if size < 1024:
        return f'{size} B'
    if size < 1024 ** 2:
        return f'{size / 1024:.1f} KB'
    return f'{size / (1024 ** 2):.1f} MB'


def week_label(week):
    year, interval = week.split('/', 1)
    return interval.replace('Semana_', '').replace('_a_', ' a ').replace('-', '/') + f'/{year}'


def initialize_upload(raw):
    digest = hashlib.sha256(raw).hexdigest()
    if st.session_state.get('upload_digest') == digest:
        return
    records, contents = analyze_zip(raw)
    st.session_state['upload_digest'] = digest
    st.session_state['records'] = records
    st.session_state['contents'] = contents
    st.session_state['critical_ids'] = set()
    st.session_state['included_ids'] = {record['id'] for record in records}
    st.session_state['prepared_zip'] = None
    st.session_state['prepared_signature'] = None
    st.session_state['editor_version'] = st.session_state.get('editor_version', 0) + 1


def set_file_choice(file_id, field, value):
    state_key = 'critical_ids' if field == 'critico' else 'included_ids'
    updated = set(st.session_state[state_key])
    if value:
        updated.add(file_id)
    else:
        updated.discard(file_id)
    st.session_state[state_key] = updated
    st.session_state['prepared_zip'] = None
    st.session_state['prepared_signature'] = None


def set_folder_included(ids, include):
    updated = set(st.session_state['included_ids'])
    if include:
        updated.update(ids)
    else:
        updated.difference_update(ids)
    st.session_state['included_ids'] = updated
    st.session_state['prepared_zip'] = None
    st.session_state['prepared_signature'] = None
    st.rerun()


st.title('Organizador de Arquivos')
st.caption('Organize, confira e exporte seus arquivos com segurança.')
st.caption('Seus arquivos originais não são alterados. As semanas utilizam a data de modificação registrada no ZIP.')
upload = st.file_uploader('Selecione um arquivo ZIP para analisar', type=['zip'])
if upload is None:
    st.stop()

try:
    initialize_upload(upload.getvalue())
except Exception as exc:
    st.error(f'Não foi possível analisar o ZIP: {exc}')
    st.stop()

records = st.session_state['records']
contents = st.session_state['contents']
critical_ids = st.session_state['critical_ids']
included_ids = st.session_state['included_ids']
info = summary(records)

st.markdown(
    f"**{info['total']}** arquivos analisados &nbsp; · &nbsp; "
    f"**{info['duplicados']}** duplicados &nbsp; · &nbsp; "
    f"**{info['semanas']}** semanas &nbsp; · &nbsp; "
    f"**{len(critical_ids)}** críticos &nbsp; · &nbsp; "
    f"**{len(included_ids)}** selecionados"
)
st.divider()

st.subheader('1. Pesquisar e conferir')
st.caption('Pesquise, filtre e marque arquivos críticos. Na prévia abaixo, você também pode incluir ou excluir arquivos da exportação.')
search_col, week_col, type_col, status_col = st.columns([2, 1.5, 1.5, 1.5])
with search_col:
    search = st.text_input('Pesquisar arquivo', placeholder='Nome do arquivo...')
with week_col:
    week_options = ['Todas'] + sorted({r['semana'] for r in records})
    week_filter = st.selectbox('Semana', week_options, format_func=lambda v: v if v == 'Todas' else week_label(v))
with type_col:
    type_filter = st.selectbox('Tipo', ['Todos'] + sorted({r['tipo'] for r in records}))
with status_col:
    status_filter = st.selectbox('Status', ['Todos', 'Duplicados', 'Unicos', 'Criticos', 'Excluidos'])

filtered = []
for record in records:
    if search.casefold() not in record['nome'].casefold():
        continue
    if week_filter != 'Todas' and record['semana'] != week_filter:
        continue
    if type_filter != 'Todos' and record['tipo'] != type_filter:
        continue
    if status_filter == 'Duplicados' and not record['duplicado']:
        continue
    if status_filter == 'Unicos' and record['duplicado']:
        continue
    if status_filter == 'Criticos' and record['id'] not in critical_ids:
        continue
    if status_filter == 'Excluidos' and record['id'] in included_ids:
        continue
    filtered.append(record)

st.caption(f'Exibindo {len(filtered)} de {len(records)} arquivos.')
frame = pd.DataFrame([{
    'ID': r['id'], 'Crítico': r['id'] in critical_ids,
    'Incluir': r['id'] in included_ids, 'Arquivo': r['nome'],
    'Tipo': r['tipo'], 'Semana': week_label(r['semana']),
    'Tamanho': pretty_size(r['tamanho']),
    'Duplicado': 'Sim' if r['duplicado'] else 'Não',
} for r in filtered], columns=['ID', 'Crítico', 'Incluir', 'Arquivo', 'Tipo', 'Semana', 'Tamanho', 'Duplicado'])

edited = st.data_editor(
    frame, hide_index=True, use_container_width=True,
    key=f"files_editor_{st.session_state['editor_version']}",
    disabled=['ID', 'Arquivo', 'Tipo', 'Semana', 'Tamanho', 'Duplicado'],
    column_config={'ID': None, 'Crítico': st.column_config.CheckboxColumn('Crítico'),
                   'Incluir': st.column_config.CheckboxColumn('Incluir')},
)
changed = False
for _, row in edited.iterrows():
    file_id = str(row['ID'])
    is_critical = bool(row['Crítico'])
    is_included = bool(row['Incluir'])
    if is_critical != (file_id in critical_ids):
        set_file_choice(file_id, 'critico', is_critical)
        changed = True
    if is_included != (file_id in included_ids):
        set_file_choice(file_id, 'incluido', is_included)
        changed = True
if changed:
    st.session_state['editor_version'] += 1
    st.rerun()

st.subheader('2. Revisar pastas de destino')
st.caption('Clique em uma pasta para ver os arquivos. Você pode incluir ou excluir arquivos individualmente ou por pasta. Os arquivos originais permanecem intactos.')

# Recalculate groups after editing the table.
critical_ids = st.session_state['critical_ids']
included_ids = st.session_state['included_ids']
folders = defaultdict(list)
for record in records:
    folders[folder_for(record, critical_ids)].append(record)

for folder in sorted(folders):
    group = folders[folder]
    selected_count = sum(r['id'] in included_ids for r in group)
    with st.expander(f'📁 {folder} — {selected_count}/{len(group)} incluídos'):
        left, right = st.columns([1, 1])
        with left:
            if st.button('Incluir todos desta pasta', key=f'include_{folder}', use_container_width=True):
                set_folder_included([r['id'] for r in group], True)
        with right:
            if st.button('Excluir todos desta pasta', key=f'exclude_{folder}', use_container_width=True):
                set_folder_included([r['id'] for r in group], False)
        for record in group:
            file_id = record['id']
            col_name, col_critical, col_included = st.columns([5, 1.3, 1.3])
            with col_name:
                duplicate_tag = ' · Duplicado' if record['duplicado'] else ''
                st.markdown(f"**{record['nome']}**  \n:gray[{record['tipo']} · {pretty_size(record['tamanho'])} · {week_label(record['semana'])}{duplicate_tag}]")
            with col_critical:
                critical = st.checkbox('Crítico', value=file_id in critical_ids, key=f"critical_{file_id}_{st.session_state['editor_version']}")
                if critical != (file_id in critical_ids):
                    set_file_choice(file_id, 'critico', critical)
                    st.session_state['editor_version'] += 1
                    st.rerun()
            with col_included:
                included = st.checkbox('Incluir', value=file_id in included_ids, key=f"included_{file_id}_{st.session_state['editor_version']}")
                if included != (file_id in included_ids):
                    set_file_choice(file_id, 'incluido', included)
                    st.session_state['editor_version'] += 1
                    st.rerun()

st.divider()
st.subheader('3. Exportar arquivos')
st.write(f"**{len(included_ids)}** arquivo(s) serão exportados; **{len(records) - len(included_ids)}** ficarão fora do ZIP organizado e constarão no relatório CSV.")
if not included_ids:
    st.warning('Nenhum arquivo selecionado. Você ainda pode gerar um ZIP contendo apenas o relatório de conferência.')

signature = (st.session_state['upload_digest'], tuple(sorted(critical_ids)), tuple(sorted(included_ids)))
if st.button('Preparar arquivos organizados', type='primary'):
    try:
        st.session_state['prepared_zip'] = export_zip(records, contents, critical_ids, included_ids)
        st.session_state['prepared_signature'] = signature
        st.success('ZIP gerado. Confira o download abaixo.')
    except Exception as exc:
        st.error(f'Falha ao gerar o ZIP: {exc}')

if st.session_state.get('prepared_zip') is not None and st.session_state.get('prepared_signature') == signature:
    st.download_button(
        'Baixar Arquivos_Organizados.zip',
        data=st.session_state['prepared_zip'],
        file_name='Arquivos_Organizados.zip', mime='application/zip',
        type='primary',
    )
