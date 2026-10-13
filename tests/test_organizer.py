import csv
import io
import unittest
import zipfile
from datetime import datetime

from core.organizer import analyze_zip, category_for, export_zip, folder_for, week_for


def make_zip(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 21, 10, 0, 0))
            archive.writestr(info, data)
    return output.getvalue()


class OrganizerTests(unittest.TestCase):
    def test_categories_and_week(self):
        self.assertEqual(category_for('dados.CSV'), 'Planilhas')
        self.assertEqual(category_for('foto.png'), 'Imagens')
        self.assertEqual(week_for(datetime(2026, 9, 23)), '2026/Semana_21-09_a_27-09')

    def test_export_folders_exclusions_and_report(self):
        raw = make_zip([('relatorio.txt', b'abc'), ('dados.csv', b'1;2'), ('foto.png', b'img')])
        records, contents = analyze_zip(raw)
        included = {records[0]['id'], records[1]['id']}
        critical = {records[1]['id']}
        with zipfile.ZipFile(io.BytesIO(export_zip(records, contents, critical, included))) as result:
            names = result.namelist()
            self.assertIn('02_Semana_21-09_a_27-09-2026/Documentos/relatorio.txt', names)
            self.assertIn('01_Arquivos_Criticos/Planilhas/dados.csv', names)
            self.assertFalse(any(name.endswith('foto.png') for name in names))
            rows = list(csv.DictReader(io.StringIO(result.read('Relatorio_Geral.csv').decode('utf-8-sig')), delimiter=';'))
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[2]['Incluido no ZIP'], 'Nao')
            self.assertTrue(rows[2]['Motivo da exclusao'])

    def test_duplicates(self):
        records, contents = analyze_zip(make_zip([('a.txt', b'same'), ('b.txt', b'same')]))
        self.assertTrue(all(r['duplicado'] for r in records))
        self.assertTrue(all(folder_for(r, set()).startswith('03_Duplicados_Para_Revisao/Documentos') for r in records))

    def test_unsafe_zip(self):
        with self.assertRaises(ValueError):
            analyze_zip(make_zip([('../inseguro.txt', b'x')]))

    def test_invalid_zip(self):
        with self.assertRaises(ValueError):
            analyze_zip(b'not a zip')


if __name__ == '__main__':
    unittest.main()
