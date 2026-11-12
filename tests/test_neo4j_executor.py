"""Executor fixtures only: a fake driver stands in for Neo4j, so no database is required."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('neo4j_executor', ROOT / 'scripts/neo4j-executor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

try:
    from neo4j import RoutingControl
    HAVE_DRIVER = True
except ImportError:  # the suite must stay green where requirements-neo4j.txt is not installed
    RoutingControl = None
    HAVE_DRIVER = False


class FakeDriver:
    """Records the call instead of talking to a server."""

    def __init__(self, rows=None):
        self.rows = rows if rows is not None else []
        self.calls = []
        self.closed = False

    def execute_query(self, query, parameters=None, **kwargs):
        self.calls.append({'query': query, 'parameters': parameters, 'kwargs': kwargs})
        return self.rows

    def close(self):
        self.closed = True


def relationship(**overrides):
    row = {
        'type': 'GOVERNS',
        'relation_id': 'R_sample_003',
        'source': 'C_referential_integrity',
        'target': 'C_foreign_key',
        'review_status': 'accepted',
        'assertion_kind': 'explicit',
        'evidence_chunk_ids': ['D03_C001'],
        'evidence_quotes_json': json.dumps(
            [{'chunk_id': 'D03_C001', 'quote': 'a foreign key must have a matching primary key'}],
            ensure_ascii=False),
    }
    row.update(overrides)
    return row


def node(identifier, label='Concept', **overrides):
    row = {'label': label, 'id': identifier, 'name': identifier, 'name_pt': identifier,
           'canonical_name': identifier}
    row.update(overrides)
    return row


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_defaults_and_environment_precedence(self):
        (self.root / '.env').write_text('NEO4J_PASSWORD=from-file\nNEO4J_URI=bolt://from-file\n',
                                        encoding='utf-8')
        with mock.patch.dict(os.environ, {'NEO4J_URI': 'bolt://from-env'}, clear=False):
            config = m.load_config(self.root)
        self.assertEqual(config['NEO4J_URI'], 'bolt://from-env')
        self.assertEqual(config['NEO4J_USER'], 'neo4j')
        self.assertEqual(config['NEO4J_DATABASE'], 'neo4j')
        self.assertEqual(config['NEO4J_PASSWORD'], 'from-file')

    def test_missing_password_is_an_explicit_error(self):
        with mock.patch.dict(os.environ, {'NEO4J_PASSWORD': ''}, clear=False):
            with self.assertRaises(m.ExecutorError) as caught:
                m.load_config(self.root)
        self.assertIn('NEO4J_PASSWORD', str(caught.exception))

    def test_only_known_keys_are_read_and_the_password_is_redacted(self):
        (self.root / '.env').write_text('NEO4J_PASSWORD=segredo-do-arquivo\nGEMINI_API_KEY=x\n',
                                        encoding='utf-8')
        config = m.load_config(self.root)
        self.assertNotIn('GEMINI_API_KEY', config)
        self.assertNotIn('segredo-do-arquivo', json.dumps(m.redact(config)))
        self.assertEqual(m.redact(config)['password'], '***')


@unittest.skipUnless(HAVE_DRIVER, 'driver neo4j ausente')
class ReadTests(unittest.TestCase):
    def test_execution_uses_read_routing_database_and_timeout(self):
        driver = FakeDriver([{'n': 1}])
        rows = m.read_rows(driver, 'MATCH (n:Concept) RETURN n LIMIT $limit',
                           {'limit': 1}, 'neo4j', 7.5)
        self.assertEqual(rows, [{'n': 1}])
        call = driver.calls[0]
        self.assertEqual(call['kwargs']['routing_'], RoutingControl.READ)
        self.assertEqual(call['kwargs']['database_'], 'neo4j')
        self.assertEqual(call['kwargs']['timeout'], 7.5)

    def test_invalid_plan_never_reaches_the_database(self):
        driver = FakeDriver()
        with self.assertRaises(m.guard.InvalidPlan):
            m.execute_plan(driver, {'start': {'label': 'Concept', 'id': 'C_join'}, 'hops': []},
                           'neo4j')
        self.assertEqual(driver.calls, [])

    def test_execute_plan_compiles_before_sending(self):
        driver = FakeDriver([{'nodes': [], 'relationships': []}])
        plan = {'start': {'label': 'Concept', 'id': 'C_join'},
                'hops': [{'direction': 'out', 'types': ['HAS_FORM'], 'target_label': 'Concept'}]}
        executed = m.execute_plan(driver, plan, 'neo4j')
        self.assertIn('LIMIT $limit', executed['cypher'])
        self.assertEqual(executed['parameters']['id_0'], 'C_join')
        self.assertEqual(driver.calls[0]['query'], executed['cypher'])

    def test_chunk_metadata_is_validated_and_idempotent_on_empty_input(self):
        driver = FakeDriver([{'chunk_id': 'D03_C001', 'document_id': 'D03',
                              'source_url': 'https://example.org', 'section_path': ['c'],
                              'title': 't'}])
        metadata = m.chunk_metadata(driver, ['D03_C001', 'D03_C001'], 'neo4j')
        self.assertEqual(metadata['D03_C001']['document_id'], 'D03')
        self.assertIn('LIMIT $limit', driver.calls[0]['query'])
        self.assertEqual(driver.calls[0]['parameters']['chunk_ids'], ['D03_C001'])
        self.assertEqual(len(driver.calls), 1)
        self.assertEqual(m.chunk_metadata(driver, [], 'neo4j'), {})
        self.assertEqual(len(driver.calls), 1)


class BundleTests(unittest.TestCase):
    def metadata(self):
        return {'D03_C001': {'chunk_id': 'D03_C001', 'document_id': 'D03',
                             'title': 'Chapter 9 Integrity Rules and Constraints',
                             'source_url': 'https://example.org/d03',
                             'section_path': ['Chapter 9']}}

    def rows(self):
        return [{'nodes': [node('C_referential_integrity', name_pt='integridade referencial'),
                           node('C_foreign_key', name_pt='chave estrangeira')],
                 'relationships': [relationship()]}]

    def test_evidence_carries_literal_quote_relation_and_source(self):
        bundle = m.bundle_from_paths('Como a integridade referencial se relaciona?',
                                     self.rows(), self.metadata())
        self.assertEqual(len(bundle['evidence']), 1)
        item = bundle['evidence'][0]
        self.assertEqual(item['chunk_id'], 'D03_C001')
        self.assertEqual(item['document_id'], 'D03')
        self.assertEqual(item['source_url'], 'https://example.org/d03')
        self.assertEqual(item['review_status'], 'accepted')
        self.assertEqual(item['origin'], 'graph')
        self.assertEqual(item['relation']['type'], 'GOVERNS')
        self.assertEqual(item['relation']['source'], 'C_referential_integrity')
        self.assertTrue(item['quote'].startswith('a foreign key must have'))
        self.assertEqual(bundle['retrieval']['channels'], ['graph'])
        self.assertFalse(bundle['retrieval']['graph_executed'] is False)
        self.assertEqual([c['concept_id'] for c in bundle['concepts']],
                         ['C_referential_integrity', 'C_foreign_key'])

    def test_bundle_is_accepted_by_the_grounding_contract(self):
        grounding_spec = importlib.util.spec_from_file_location(
            'answer_grounding', ROOT / 'scripts/answer-grounding.py')
        grounding = importlib.util.module_from_spec(grounding_spec)
        grounding_spec.loader.exec_module(grounding)
        bundle = m.bundle_from_paths('Pergunta?', self.rows(), self.metadata())
        normalized = grounding.normalize_bundle(bundle)
        self.assertEqual(normalized['evidence'][0]['evidence_id'], 'E1')
        self.assertEqual(normalized['question'], 'Pergunta?')

    def test_duplicate_quotes_across_relationships_become_one_evidence_item(self):
        rows = [{'nodes': [], 'relationships': [relationship(), relationship()]}]
        bundle = m.bundle_from_paths('Pergunta?', rows, self.metadata())
        self.assertEqual(len(bundle['evidence']), 1)

    def test_hops_are_reported_from_the_shortest_returned_path(self):
        rows = [{'nodes': [], 'relationships': [relationship(), relationship(type='IS_A'),
                                                relationship(type='SUPPORTS')]}]
        bundle = m.bundle_from_paths('Pergunta?', rows, self.metadata())
        self.assertEqual(bundle['retrieval']['max_hops'], 3)

    def test_paths_without_relationships_produce_no_evidence(self):
        bundle = m.bundle_from_paths('Pergunta?', [{'nodes': [], 'relationships': []}], {})
        self.assertEqual(bundle['evidence'], [])
        self.assertEqual(bundle['concepts'], [])

    def test_stored_evidence_is_never_repaired(self):
        broken = relationship(evidence_quotes_json='{not json')
        with self.assertRaises(m.ExecutorError):
            m.bundle_from_paths('Pergunta?', [{'nodes': [], 'relationships': [broken]}], {})
        empty = relationship(evidence_quotes_json=json.dumps([{'chunk_id': 'D03_C001'}]))
        with self.assertRaises(m.ExecutorError):
            m.bundle_from_paths('Pergunta?', [{'nodes': [], 'relationships': [empty]}], {})

    def test_evidence_chunk_ids_are_unique_and_ordered(self):
        rows = [{'relationships': [relationship(evidence_chunk_ids=['D03_C001', 'D07_C002'])],
                 'nodes': []},
                {'relationships': [relationship(evidence_chunk_ids=['D07_C002'])], 'nodes': []}]
        self.assertEqual(m.evidence_chunk_ids(rows), ['D03_C001', 'D07_C002'])

    def test_projection_without_evidence_is_ignored(self):
        rows = [{'nodes': [node('C_join')], 'relationships': ['HAS_FORM']}]
        bundle = m.bundle_from_paths('Pergunta?', rows, {})
        self.assertEqual(bundle['evidence'], [])
        self.assertEqual(len(bundle['concepts']), 1)


if __name__ == '__main__':
    unittest.main()
