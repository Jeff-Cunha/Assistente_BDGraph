import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sql_terms', ROOT / 'scripts/extract-sql-terms.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SQLTermsTests(unittest.TestCase):
    def chunk(self, text):
        return dict(chunk_id='D06_C001', document_id='D06', text=text, source_url='https://example.org')

    def test_boolean_or_not_detected_as_english_conjunction(self):
        rows = m.find_occurrences([self.chunk('Some rows or columns are mentioned here.')])
        self.assertNotIn('C_or', [r['concept_id'] for r in rows])

    def test_matching_does_not_use_substrings(self):
        rows = m.find_occurrences([self.chunk('selection and summary are ordinary words.')])
        self.assertEqual(rows, [])

    def test_code_context_and_exact_offsets_preserved(self):
        c = self.chunk('An example:\n\n```sql\nSELECT * FROM table1;\n```')
        rows = m.find_occurrences([c])
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(c['text'][r['start']:r['end']], r['quote'])
            self.assertTrue(r['code_context'])

    def test_non_sql_source_not_scanned(self):
        c = self.chunk('SELECT');c['document_id'] = 'D01'
        self.assertEqual(m.find_occurrences([c]), [])


if __name__ == '__main__':
    unittest.main()
