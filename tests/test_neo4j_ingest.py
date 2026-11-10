"""Testes da ingestão no Neo4j. Os testes sem banco rodam sempre; os de banco exigem NEO4J_TEST=1."""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('neo4j_ingest', ROOT / 'scripts/neo4j_ingest.py')
ingest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingest)

RULE = 'data/extraction/rule-knowledge-union-v2/extraction.json'
NEEDED = ['data/release/current.json', 'data/extraction/rule-knowledge-union-v2/extraction.json',
          'data/extraction/model-knowledge-union-v3/extraction.json',
          'data/extraction/manual-source-review-v1/extraction.json', 'data/extraction/sample.json',
          'corpus/metadata/sources.json', 'corpus/chunks/chunks.jsonl', 'corpus/chunks/figure_supplements.jsonl']


def copy_inputs(target):
    for rel in NEEDED:
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, target / rel)


class PayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = ingest.build_payload(ROOT)
        cls.with_sample = ingest.build_payload(ROOT, include_sample=True)

    def test_counts_match_the_release_index(self):
        self.assertEqual(dict(ingest.expected_counts(self.base)), {
            'Document': 9, 'Chunk': 59, 'Concept': 93, 'CONTAINS': 59, 'SUPPLEMENTS': 28,
            'MENTIONS': 130, 'semantic': 16})

    def test_sample_only_adds_relations_never_concepts(self):
        counts = ingest.expected_counts(self.with_sample)
        self.assertEqual((counts['Concept'], counts['semantic']), (93, 23))

    def test_shared_concepts_are_united_not_overwritten(self):
        concept = {c['concept_id']: c for c in self.base['concepts']}['C_aggregate_function']
        self.assertEqual(set(concept['extraction_methods']), {'rule_candidates', 'llm_candidates'})
        self.assertTrue({'aggregate functions', 'aggregates'} <= set(concept['aliases']))
        provenance = json.loads(concept['provenance_json'])
        self.assertEqual({p['method'] for p in provenance}, {'rule_candidates', 'llm_candidates'})

    def test_text_fields_come_from_first_file_and_sample_never_wins(self):
        rule = {c['concept_id']: c for c in json.loads((ROOT / RULE).read_text(encoding='utf-8'))['concepts']}
        for payload in (self.base, self.with_sample):
            row = {c['concept_id']: c for c in payload['concepts']}['C_row']
            self.assertEqual(row['description_pt'], rule['C_row']['description_pt'])
        base = {c['concept_id']: c['description_pt'] for c in self.base['concepts']}
        sampled = {c['concept_id']: c['description_pt'] for c in self.with_sample['concepts']}
        self.assertEqual(base, sampled)

    def test_nested_values_become_json_and_nulls_are_dropped(self):
        props = ingest.neo_props({'a': 1, 'b': ['x', 'y'], 'c': [['x']], 'd': {'k': 1}, 'e': None, 'f': []})
        self.assertEqual(props['a'], 1)
        self.assertEqual(props['b'], ['x', 'y'])
        self.assertEqual(json.loads(props['c_json']), [['x']])
        self.assertEqual(json.loads(props['d_json']), {'k': 1})
        self.assertNotIn('e', props)
        self.assertEqual(props['f'], [])

    def test_figure_chunks_keep_status_and_parents(self):
        figures = [c for c in self.base['chunks'] if c['content_type'] == 'figure_transcription']
        self.assertEqual(len(figures), 28)
        self.assertEqual(sum(1 for c in figures if c['transcription_status'] == 'partial'), 2)
        self.assertTrue(all(isinstance(c['parent_chunk_ids'], list) for c in figures))

    def test_page_chunks_default_to_page_text(self):
        pages = [c for c in self.base['chunks'] if c['content_type'] == 'page_text']
        self.assertEqual(len(pages), 31)


class InvalidDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        copy_inputs(self.tmp)

    def test_all_reference_problems_are_reported_together(self):
        path = self.tmp / RULE
        data = json.loads(path.read_text(encoding='utf-8'))
        data['relations'].append({
            'relation_id': 'R_x', 'source': 'C_avg', 'type': 'DROP_EVERYTHING', 'target': 'C_inexistente',
            'assertion_kind': 'explicit', 'review_status': 'accepted',
            'evidence': [{'chunk_id': 'D99_C001', 'quote': 'não existe'}]})
        data['concepts'][0]['evidence'] = [{'chunk_id': 'D08_C001', 'quote': 'citação inventada'}]
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        with self.assertRaises(ingest.IngestError) as ctx:
            ingest.build_payload(self.tmp, check_hashes=False)
        message = str(ctx.exception)
        for expected in ('fora da lista permitida', 'conceito inexistente C_inexistente',
                         'chunk inexistente D99_C001', 'não está literalmente'):
            self.assertIn(expected, message)

    def test_changed_release_file_is_detected_by_hash(self):
        path = self.tmp / RULE
        path.write_text(path.read_text(encoding='utf-8') + '\n', encoding='utf-8')
        with self.assertRaises(ingest.IngestError) as ctx:
            ingest.build_payload(self.tmp)
        self.assertIn('Hash diferente', str(ctx.exception))

    def test_divergent_identity_between_files_is_an_error(self):
        path = self.tmp / 'data/extraction/model-knowledge-union-v3/extraction.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['concepts'][0]['category'] = 'structure' if data['concepts'][0]['category'] != 'structure' else 'general'
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        with self.assertRaises(ingest.IngestError) as ctx:
            ingest.build_payload(self.tmp, check_hashes=False)
        self.assertIn("'category' diverge", str(ctx.exception))

    def test_relation_type_outside_allowlist_never_reaches_cypher(self):
        class Boom:
            def run(self, *args, **kwargs):
                raise AssertionError('não deveria executar consulta')
        payload = {'documents': [], 'chunks': [], 'concepts': [], 'contains': [], 'supplements': [],
                   'mentions': [], 'relations': {'X}) DETACH DELETE (n': [{'source': 'a', 'target': 'b', 'props': {}}]}}
        with self.assertRaises(ingest.IngestError):
            ingest.write_payload(Boom(), payload)


@unittest.skipUnless(os.environ.get('NEO4J_TEST') == '1', 'defina NEO4J_TEST=1 (e a conexão no .env) para testar com banco')
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = ingest.connect(wait=30)
        cls.database = os.environ.get('NEO4J_DATABASE', 'neo4j')
        cls.payload = ingest.build_payload(ROOT, include_sample=True)
        with cls.driver.session(database=cls.database) as session:
            ingest.apply_schema(session)

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()

    def snapshot(self, session):
        nodes = session.run('MATCH (n) RETURN labels(n)[0] AS k, count(n) AS n ORDER BY k').data()
        rels = session.run('MATCH ()-[r]->() RETURN type(r) AS k, count(r) AS n ORDER BY k').data()
        return nodes, rels

    def test_running_twice_changes_nothing_and_keeps_other_parts_properties(self):
        with self.driver.session(database=self.database) as session:
            session.execute_write(ingest.write_payload, self.payload)
            session.run("MATCH (c:Chunk {chunk_id: 'D03_C001'}) SET c.embedding = [0.1, 0.2]").consume()
            first = self.snapshot(session)
            session.execute_write(ingest.write_payload, self.payload)
            self.assertEqual(first, self.snapshot(session))
            kept = session.run("MATCH (c:Chunk {chunk_id: 'D03_C001'}) RETURN c.embedding AS e").single()['e']
            self.assertEqual(kept, [0.1, 0.2])
            self.assertTrue(all(ok for ok, _ in ingest.verify(session, self.payload)))

    def test_invalid_reference_rolls_back_the_whole_load(self):
        broken = dict(self.payload)
        broken['concepts'] = self.payload['concepts'] + [{'concept_id': 'C_zz_rollback_test', 'canonical_name': 'x'}]
        broken['mentions'] = self.payload['mentions'] + [{'chunk_id': 'D99_C999', 'concept_id': 'C_zz_rollback_test'}]
        with self.driver.session(database=self.database) as session:
            with self.assertRaises(ingest.IngestError):
                session.execute_write(ingest.write_payload, broken)
            left = session.run("MATCH (c:Concept {concept_id: 'C_zz_rollback_test'}) RETURN count(c) AS n").single()['n']
            self.assertEqual(left, 0)


if __name__ == '__main__':
    unittest.main()
