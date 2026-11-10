import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('glossary_review', ROOT / 'scripts/export-glossary-review.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class GlossaryReviewTests(unittest.TestCase):
    def setUp(self):
        self.quote = '<strong>table</strong>: source definition'
        self.entries = [dict(candidate_id='G1', surface='table', chunk_id='T1', quote=self.quote,
                             start=0, end=len(self.quote))]
        self.chunks = {'T1': {'text': self.quote}}
        self.review = dict(concepts={'C_table': dict(canonical_name='table', name_pt='tabela', aliases=[],
            category='structure', description_pt='Descrição revisada.')},
            decisions=[dict(candidate_id='G1', decision='accept', concept_id='C_table', note='Reviewed.')])

    def test_approved_source_is_preserved_and_method_is_honest(self):
        out = m.export(self.entries, self.review, self.chunks)
        self.assertEqual(out['extraction_method'], 'rule_candidates')
        self.assertEqual(out['concepts'][0]['evidence'][0]['quote'], self.quote)
        self.assertEqual(out['relations'], [])

    def test_missing_decision_rejected(self):
        self.review['decisions'] = []
        with self.assertRaises(ValueError):
            m.export(self.entries, self.review, self.chunks)

    def test_mapping_must_preserve_source_surface(self):
        self.review['concepts']['C_table']['canonical_name'] = 'row'
        with self.assertRaises(ValueError):
            m.export(self.entries, self.review, self.chunks)

    def test_changed_source_offsets_rejected(self):
        self.entries[0]['end'] -= 1
        with self.assertRaises(ValueError):
            m.export(self.entries, self.review, self.chunks)

    def test_flags_not_promoted_to_accepted_concepts(self):
        second = copy.deepcopy(self.entries[0]); second['candidate_id'] = 'G2'
        self.entries.append(second)
        self.review['decisions'].append(dict(candidate_id='G2', decision='flag', note='Pending source issue.'))
        out = m.export(self.entries, self.review, self.chunks)
        self.assertEqual(len(out['concepts']), 1)
        self.assertEqual(len(out['concepts'][0]['evidence']), 1)


if __name__ == '__main__':
    unittest.main()
