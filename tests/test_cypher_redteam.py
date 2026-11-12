"""Red-team fixtures: every attack and control in data/llm/testes is exercised here.

The file is data, not code, so new attempts can be added without touching the validator.
"""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('guard_cypher', ROOT / 'scripts/guard-cypher.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FIXTURES = ROOT / 'data/llm/testes/cypher-ataques.jsonl'


def load():
    return [json.loads(line) for line in FIXTURES.read_text(encoding='utf-8').splitlines()
            if line.strip()]


class RedTeamTests(unittest.TestCase):
    def setUp(self):
        self.cases = load()

    def test_fixture_file_is_well_formed_and_has_both_directions(self):
        self.assertGreaterEqual(len(self.cases), 30)
        identifiers = [case['id'] for case in self.cases]
        self.assertEqual(len(identifiers), len(set(identifiers)), 'IDs repetidos')
        self.assertTrue(any(case['esperado'] == 'aceitar' for case in self.cases))
        self.assertTrue(any(case['esperado'] == 'rejeitar' for case in self.cases))
        for case in self.cases:
            self.assertIn(case['esperado'], ('aceitar', 'rejeitar'))
            self.assertTrue(case['categoria'])
            self.assertTrue(case['cypher'])
            if case['esperado'] == 'rejeitar':
                self.assertTrue(case['regra'], f"{case['id']} sem regra esperada")

    def test_every_rejection_states_its_rule(self):
        for case in self.cases:
            if case['esperado'] != 'rejeitar':
                continue
            with self.subTest(case=case['id'], categoria=case['categoria']):
                with self.assertRaises(m.UnsafeCypher) as caught:
                    m.validate_cypher(case['cypher'], case.get('parametros') or {})
                self.assertIn(case['regra'], str(caught.exception))

    def test_controls_are_accepted(self):
        for case in self.cases:
            if case['esperado'] != 'aceitar':
                continue
            with self.subTest(case=case['id'], categoria=case['categoria']):
                result = m.validate_cypher(case['cypher'], case.get('parametros') or {})
                self.assertIn('RETURN', result['query'])
                self.assertIsNotNone(result['limit'])

    def test_no_case_can_reach_writes_procedures_or_vectors(self):
        """Independent of the expected field: nothing may pass with these constructs."""
        forbidden = ('CREATE', 'MERGE', 'DELETE', 'SET', 'REMOVE', 'CALL', 'LOAD CSV',
                     'embedding', '.password', 'RETURN *')
        for case in self.cases:
            query = case['cypher'].upper()
            if not any(word.upper() in query for word in forbidden):
                continue
            with self.subTest(case=case['id']):
                with self.assertRaises(m.UnsafeCypher):
                    m.validate_cypher(case['cypher'], case.get('parametros') or {})


if __name__ == '__main__':
    unittest.main()
