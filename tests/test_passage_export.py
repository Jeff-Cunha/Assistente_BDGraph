import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('export_review', ROOT / 'scripts/export-passage-review.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ReviewExportTests(unittest.TestCase):
    def setUp(self):
        self.text = 'entity integrity requires a primary key'
        self.batch = {'runs': [{'passage_id': 'P1', 'status': 'passed_model_check_pending_review',
            'is_synthetic_control': False, 'relations': [{'source': 'entity integrity', 'type': 'REQUIRES',
                'target': 'primary key', 'evidence': {'chunk_id': 'T1', 'quote': self.text,
                'start': 0, 'end': len(self.text)}}]}]}
        self.review = {'concepts': {
            'C_entity_integrity': dict(canonical_name='entity integrity', name_pt='integridade de entidade',
                aliases=[], category='constraint', description_pt='Regra.'),
            'C_primary_key': dict(canonical_name='primary key', name_pt='chave primária',
                aliases=[], category='structure', description_pt='Chave.')},
            'decisions': [dict(passage_id='P1', decision='accept', expected_type='REQUIRES', note='Conferido.',
                source_concept_id='C_entity_integrity', target_concept_id='C_primary_key')]}
        self.chunks = {'T1': {'text': self.text}}

    def test_exports_exact_evidence(self):
        out = m.export(self.batch, self.review, self.chunks)
        self.assertEqual(out['relations'][0]['evidence'][0]['quote'], self.text)
        self.assertEqual(len(out['concepts']), 2)

    def test_synthetic_control_cannot_be_approved(self):
        self.batch['runs'][0]['is_synthetic_control'] = True
        with self.assertRaises(ValueError):
            m.export(self.batch, self.review, self.chunks)

    def test_every_passage_needs_a_decision(self):
        second = copy.deepcopy(self.batch['runs'][0])
        second['passage_id'] = 'P2'
        self.batch['runs'].append(second)
        with self.assertRaises(ValueError):
            m.export(self.batch, self.review, self.chunks)

    def test_offset_tampering_is_rejected(self):
        self.batch['runs'][0]['relations'][0]['evidence']['end'] -= 1
        with self.assertRaises(ValueError):
            m.export(self.batch, self.review, self.chunks)

    def test_mapping_cannot_silently_change_endpoint(self):
        self.review['concepts']['C_primary_key']['canonical_name'] = 'foreign key'
        with self.assertRaises(ValueError):
            m.export(self.batch, self.review, self.chunks)

    def test_existing_relation_id_is_preserved(self):
        known = [{'source': 'C_entity_integrity', 'type': 'REQUIRES',
                  'target': 'C_primary_key', 'relation_id': 'R_existing'}]
        out = m.export(self.batch, self.review, self.chunks, known)
        self.assertEqual(out['relations'][0]['relation_id'], 'R_existing')

    def test_predicate_change_after_review_is_rejected(self):
        self.batch['runs'][0]['relations'][0]['type'] = 'IS_A'
        with self.assertRaises(ValueError):
            m.export(self.batch, self.review, self.chunks)


if __name__ == '__main__':
    unittest.main()
