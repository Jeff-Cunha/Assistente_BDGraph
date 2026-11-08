"""Synthetic structural fixtures only; not extraction quality benchmarks."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('consolidation', ROOT / 'scripts/consolidate-extraction.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SCHEMA = json.loads((ROOT / 'schemas/extraction-candidates.schema.json').read_text())


def concept(local_id='L1', name='foreign key', aliases=None, existing=None):
    return {'local_id': local_id, 'existing_concept_id': existing, 'canonical_name': name,
            'name_pt': name, 'aliases': aliases or [], 'category': 'structure',
            'description_pt': 'Descrição para teste estrutural.',
            'evidence': [{'chunk_id': 'T1', 'quote': 'foreign key'}],
            'review_status': 'pending', 'review_note': ''}


def fixture():
    return {'chunk_id': 'T1', 'concepts': [concept()], 'relations': [], 'issues': []}


class ConsolidationTests(unittest.TestCase):
    def run_case(self, candidates, registry=None):
        chunks = {'T1': {'text': 'foreign key join'}, 'T2': {'text': 'foreign key join'}}
        return module.consolidate(candidates, chunks, registry or [], SCHEMA)

    def test_merge_exact_name_accumulates_evidence_and_is_deterministic(self):
        a, b = fixture(), fixture()
        b['chunk_id'] = 'T2'
        b['concepts'][0]['evidence'][0]['chunk_id'] = 'T2'
        first, _ = self.run_case([a, b])
        second, _ = self.run_case([b, a])
        self.assertEqual(first, second)
        self.assertEqual(len(first['concepts']), 1)
        self.assertEqual(len(first['concepts'][0]['evidence']), 2)
        self.assertEqual(first['concepts'][0]['review_status'], 'pending')

    def test_shared_alias_flags_but_does_not_merge(self):
        a = fixture()
        a['concepts'][0]['aliases'] = ['ambiguous']
        a['concepts'].append(concept('L2', 'join', ['ambiguous']))
        result, review = self.run_case([a])
        self.assertEqual(len(result['concepts']), 2)
        self.assertTrue(all(c['review_status'] == 'flagged' for c in result['concepts']))
        self.assertTrue(any(i['kind'] == 'ambiguous_alias' for i in review['issues']))

    def test_registry_alias_keeps_id_without_copying_seed_evidence(self):
        seed = {'concept_id': 'C_foreign_key', 'canonical_name': 'foreign key',
                'name_pt': 'chave estrangeira', 'aliases': ['FK'], 'category': 'structure',
                'evidence': [{'chunk_id': 'OTHER', 'quote': 'not current evidence'}]}
        a = fixture()
        a['concepts'][0].update(canonical_name='FK', existing_concept_id='C_foreign_key')
        result, _ = self.run_case([a], [seed])
        self.assertEqual(result['concepts'][0]['concept_id'], 'C_foreign_key')
        self.assertEqual(result['concepts'][0]['evidence'][0]['chunk_id'], 'T1')

    def test_rejects_unsupported_citation(self):
        a = fixture()
        a['concepts'][0]['evidence'][0]['quote'] = 'invented'
        with self.assertRaises(ValueError):
            self.run_case([a])

    def test_rejects_two_runs_for_same_chunk(self):
        with self.assertRaises(ValueError):
            self.run_case([fixture(), fixture()])

    def test_rejects_missing_endpoint(self):
        a = fixture()
        a['relations'] = [{'source_local_id': 'L1', 'target_local_id': 'L2', 'type': 'REQUIRES',
                           'assertion_kind': 'explicit', 'evidence': [{'chunk_id': 'T1', 'quote': 'foreign key'}],
                           'review_status': 'pending', 'review_note': ''}]
        with self.assertRaises(ValueError):
            self.run_case([a])

    def test_relations_merge_and_flag_propagates(self):
        a = fixture()
        a['concepts'].append(concept('L2', 'join'))
        a['concepts'][0].update(review_status='flagged', review_note='Needs review.')
        r = {'source_local_id': 'L1', 'target_local_id': 'L2', 'type': 'TYPICALLY_USED_IN',
             'assertion_kind': 'explicit', 'evidence': [{'chunk_id': 'T1', 'quote': 'foreign key join'}],
             'review_status': 'pending', 'review_note': ''}
        a['relations'] = [r, copy.deepcopy(r)]
        result, _ = self.run_case([a])
        self.assertEqual(len(result['relations']), 1)
        self.assertEqual(result['relations'][0]['review_status'], 'flagged')

    def test_rejects_name_mismatch_for_explicit_registry_id(self):
        seed = {'concept_id': 'C_join', 'canonical_name': 'join', 'name_pt': 'junção',
                'aliases': [], 'category': 'operation'}
        a = fixture()
        a['concepts'][0]['existing_concept_id'] = 'C_join'
        with self.assertRaises(ValueError):
            self.run_case([a], [seed])

    def test_rejects_conflicting_categories(self):
        a, b = fixture(), fixture()
        b['chunk_id'] = 'T2'
        b['concepts'][0]['evidence'][0]['chunk_id'] = 'T2'
        b['concepts'][0]['category'] = 'operation'
        with self.assertRaises(ValueError):
            self.run_case([a, b])


if __name__ == '__main__':
    unittest.main()
