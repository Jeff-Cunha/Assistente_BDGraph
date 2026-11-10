"""Display conversion must retain data and avoid inventing headers or editing SQL."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reading', ROOT / 'scripts/prepare-reading-copies.py')
reading = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reading)


class ReadingCopyTests(unittest.TestCase):
    def test_empty_and_pipe_cells_survive(self):
        rendered, status = reading.render_table('<table><tr><th>A</th><th>B</th></tr><tr><td>x|y</td><td></td></tr></table>')
        self.assertEqual(status, 'markdown_table')
        self.assertEqual(rendered, '| A | B |\n| --- | --- |\n| x\\|y |  |')

    def test_explanatory_callout_has_no_invented_header(self):
        rendered, status = reading.render_table('<table><tr><td>Explanation</td></tr></table>')
        self.assertEqual((rendered, status), ('> Explanation', 'callout'))

    def test_merged_cells_are_not_silently_flattened(self):
        original = '<table><tr><th colspan="2">Title</th></tr><tr><td>A</td><td>B</td></tr></table>'
        self.assertEqual(reading.render_table(original), (original, 'retained_unsupported_table'))

    def test_code_fences_are_preserved(self):
        original = '```sql\nSELECT \'<strong>A</strong>\', \'&gt;\';\n```\n'
        self.assertEqual(reading.convert(original)[0], original)

    def test_whitespace_in_emphasis_does_not_join_table_name_and_label(self):
        rendered, _ = reading.convert('<strong>Client_Interview2 </strong>table')
        self.assertEqual(rendered, '**Client_Interview2** table')

    def test_real_postgresql_callout_keeps_links_and_has_no_header(self):
        original = (ROOT / 'corpus/processed/D08.md').read_text(encoding='utf-8')
        rendered, counts = reading.convert(original)
        self.assertEqual(counts['callout'], 1)
        self.assertEqual(counts['retained_table_without_header'], 0)
        self.assertIn('`LIKE`', rendered)
        self.assertIn('https://www.postgresql.org/docs/18/functions-matching.html', rendered)
        self.assertNotIn('<table', rendered)

    def test_real_normalization_tables_keep_all_rows_and_cells(self):
        import re
        original = (ROOT / 'corpus/processed/D05.md').read_text(encoding='utf-8')
        blocks = re.findall(r'<table\b[^>]*>.*?</table>', original, flags=re.S)
        self.assertEqual(len(blocks), 6)
        for block in blocks:
            table = reading.Table()
            table.feed(block)
            rendered, status = reading.render_table(block)
            self.assertEqual(status, 'markdown_table')
            self.assertEqual(len(rendered.splitlines()), len(table.rows) + 1)
            for source_row, markdown_row in zip(table.rows, [rendered.splitlines()[0]] + rendered.splitlines()[2:]):
                expected = '| ' + ' | '.join(reading.cell_text(c['value']) for c in source_row) + ' |'
                self.assertEqual(markdown_row, expected)


if __name__ == '__main__':
    unittest.main()
