"""Every query plan shipped as an example must pass the guard with its own defaults.

This exists because of a real defect: the integrity/join example carried four hops while
`compile_plan()` defaulted to three while the example carried four, so a file in this
repository failed the validator in this same repository unless the caller raised the budget.
"""
import importlib.util
import inspect
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'data' / 'llm' / 'exemplos'


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load('guard_cypher', 'guard-cypher.py')
executor = _load('neo4j_executor', 'neo4j-executor.py')


def plans():
    for path in sorted(EXAMPLES.glob('*.json')):
        document = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(document, dict) and 'hops' in document and 'start' in document:
            yield path, document


class BudgetTest(unittest.TestCase):
    def test_the_budget_is_one_number(self):
        self.assertEqual(guard.DEFAULT_MAX_HOPS, 4)
        for function in (guard.validate_plan, guard.compile_plan, executor.execute_plan):
            with self.subTest(function=function.__name__):
                self.assertEqual(
                    inspect.signature(function).parameters['max_hops'].default,
                    guard.DEFAULT_MAX_HOPS)

    def test_five_hops_are_refused_by_default_and_accepted_on_request(self):
        hop = {'direction': 'out', 'types': ['HAS_FORM'], 'target_label': 'Concept'}
        plan = {'start': {'label': 'Concept', 'id': 'C_referential_integrity'},
                'hops': [dict(hop) for _ in range(5)], 'include_evidence': True, 'limit': 10}
        with self.assertRaises(guard.InvalidPlan):
            guard.compile_plan(plan)
        self.assertEqual(guard.compile_plan(plan, max_hops=5)['hops'], 5)


class ExampleTest(unittest.TestCase):
    def test_there_is_at_least_one_plan_example(self):
        self.assertTrue(list(plans()), 'nenhum plano de exemplo encontrado')

    def test_every_example_compiles_with_the_default_budget(self):
        for path, plan in plans():
            with self.subTest(example=path.name):
                compiled = guard.compile_plan(plan)
                self.assertLessEqual(compiled['hops'], guard.DEFAULT_MAX_HOPS)
                self.assertIn('LIMIT $limit', compiled['cypher'])
                self.assertEqual(compiled['parameters']['limit'], plan.get('limit', 25))

    def test_the_integrity_join_example_keeps_evidence_on_every_hop(self):
        path = EXAMPLES / 'plano-integridade-join.json'
        plan = json.loads(path.read_text(encoding='utf-8'))
        self.assertTrue(plan['include_evidence'])
        compiled = guard.compile_plan(plan)
        self.assertIn('evidence_quotes_json', compiled['cypher'])


if __name__ == '__main__':
    unittest.main()
