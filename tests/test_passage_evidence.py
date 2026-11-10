"""Evidence-integrity tests; these don't assess model semantics."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('passage_pilot', ROOT / 'scripts/pilot-passage-extraction.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class PassageEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.text = ('# Heading\n\n' +
            'To ensure <em>entity integrity</em>, it is required that every table have a primary key. '
            'Neither the PK nor any part of it can contain null values.')
        self.p = m.passages({'chunk_id': 'T1', 'text': self.text})[0]
        self.data = {'relations': [{'source': 'entity integrity', 'type': 'REQUIRES',
            'target': 'primary key', 'passage_id': self.p['passage_id']}]}

    def test_offsets_preserve_markup_exactly(self):
        self.assertEqual(self.text[self.p['start']:self.p['end']], self.p['text'])
        self.assertIn('<em>', self.p['text'])
        m.validate_selection(self.data, self.p)

    def test_unknown_evidence_id_rejected(self):
        self.data['relations'][0]['passage_id'] = 'invented'
        with self.assertRaises(ValueError):
            m.validate_selection(self.data, self.p)

    def test_unmentioned_endpoint_rejected(self):
        self.data['relations'][0]['target'] = 'foreign key'
        with self.assertRaises(ValueError):
            m.validate_selection(self.data, self.p)

    def test_no_relations_is_valid(self):
        m.validate_selection({'relations': []}, self.p)

    def test_more_than_one_relation_rejected(self):
        self.data['relations'] *= 2
        with self.assertRaises(Exception):
            m.validate_selection(self.data, self.p)

    def test_semantic_gate_requires_all_checks(self):
        decision = dict(entailed=True, direction_correct=True, endpoints_are_concepts=True,
                        conditions_preserved=True, reason='Supported.')
        self.assertTrue(m.passes_semantic_check(decision))
        for key in ('entailed', 'direction_correct', 'endpoints_are_concepts', 'conditions_preserved'):
            rejected = dict(decision, **{key: False})
            self.assertFalse(m.passes_semantic_check(rejected))

    def test_semantic_gate_rejects_truthy_string(self):
        decision = dict(entailed='true', direction_correct=True, endpoints_are_concepts=True,
                        conditions_preserved=True, reason='Invalid type.')
        with self.assertRaises(Exception):
            m.passes_semantic_check(decision)

    def test_qualified_requirement_blocked_even_if_model_would_approve(self):
        p = dict(self.p, text='Referential integrity requires that a foreign key must have a matching primary key or it must be null.')
        rel = dict(source='referential integrity', type='REQUIRES', target='foreign key')
        self.assertIsNotNone(m.qualifier_risk(rel, p))

    def test_direct_requirement_not_blocked_by_precision_policy(self):
        self.assertIsNone(m.qualifier_risk(self.data['relations'][0], self.p))

    def test_document_batch_includes_all_eligible_chunks(self):
        chunks = {'A': {'chunk_id': 'A', 'document_id': 'D03', 'text': self.text},
                  'B': {'chunk_id': 'B', 'document_id': 'D07', 'text': self.text},
                  'C': {'chunk_id': 'C', 'document_id': 'D09', 'text': self.text}}
        selected = m.select_document_passages(chunks, ['D03', 'D07'])
        self.assertEqual({p['chunk_id'] for p in selected}, {'A', 'B'})

    def test_unknown_document_rejected(self):
        with self.assertRaises(ValueError):
            m.select_document_passages({}, ['UNKNOWN'])

    def test_inline_code_normalized_for_labels_but_not_citations(self):
        p = dict(self.p, text='The `WHERE` clause filters rows using a condition.')
        data = {'relations': [dict(source='WHERE clause', type='FILTERS', target='rows', passage_id=p['passage_id'])]}
        m.validate_selection(data, p)
        self.assertIn('`WHERE`', p['text'])

    def test_having_exception_not_flattened_into_requirement(self):
        p = dict(self.p, text="The HAVING clause always contains aggregates. Strictly speaking, you may write HAVING without aggregates.")
        rel = dict(source='HAVING', type='REQUIRES', target='aggregates')
        self.assertIsNotNone(m.qualifier_risk(rel, p))


if __name__ == '__main__':
    unittest.main()
