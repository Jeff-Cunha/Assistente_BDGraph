"""Guard fixtures only; they describe the rules, not the corpus."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('guard_cypher', ROOT / 'scripts/guard-cypher.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def plan(**overrides):
    base = {
        'start': {'label': 'Concept', 'id': 'C_referential_integrity'},
        'hops': [
            {'direction': 'out', 'types': ['GOVERNS'], 'target_label': 'Concept'},
            {'direction': 'out', 'types': ['TYPICALLY_USED_IN'], 'target_label': 'Concept'},
        ],
        'include_evidence': True,
        'limit': 10,
    }
    base.update(overrides)
    return base


class CompilePlanTests(unittest.TestCase):
    def test_compiled_query_passes_its_own_validator(self):
        result = m.compile_plan(plan(), max_hops=3)
        self.assertEqual(result['labels'], ['Concept'])
        self.assertEqual(result['relationship_types'], ['GOVERNS', 'TYPICALLY_USED_IN'])
        self.assertEqual(result['parameters'], {'id_0': 'C_referential_integrity', 'limit': 10})
        self.assertIn('MATCH p=(n0:Concept {concept_id: $id_0})', result['cypher'])
        self.assertIn('-[r1:GOVERNS]->(n1:Concept)-[r2:TYPICALLY_USED_IN]->(n2:Concept)', result['cypher'])
        self.assertNotIn('C_referential_integrity', result['cypher'])

    def test_compilation_is_deterministic(self):
        self.assertEqual(m.compile_plan(plan()), m.compile_plan(plan()))

    def test_directions_render_and_validate(self):
        hops = [{'direction': 'in', 'types': ['CONTAINS'], 'target_label': 'Document'},
                {'direction': 'both', 'types': ['MENTIONS', 'SUPPORTS'], 'target_label': 'Concept'}]
        query = m.compile_plan(plan(hops=hops))['cypher']
        self.assertIn('<-[r1:CONTAINS]-(n1:Document)', query)
        self.assertIn('-[r2:MENTIONS|SUPPORTS]-(n2:Concept)', query)

    def test_four_hop_path_matches_the_documented_sample_chain(self):
        hops = [{'direction': 'out', 'types': [t], 'target_label': 'Concept'}
                for t in ('GOVERNS', 'TYPICALLY_USED_IN', 'HAS_FORM', 'HAS_FORM')]
        result = m.compile_plan(plan(hops=hops), max_hops=4)
        self.assertEqual(result['hops'], 4)
        self.assertIn('(n4:Concept)', result['cypher'])

    def test_evidence_projection_identifies_each_relationship(self):
        query = m.compile_plan(plan())['cypher']
        self.assertIn('relation_id: x.relation_id', query)
        self.assertIn('source: startNode(x).concept_id', query)
        self.assertIn('target: endNode(x).concept_id', query)
        self.assertIn('canonical_name: x.canonical_name', query)

    def test_whitelist_matches_the_properties_the_graph_stores(self):
        stored = {'concept_id', 'canonical_name', 'name_pt', 'aliases', 'category',
                  'description_pt', 'review_status', 'review_note', 'extraction_methods',
                  'evidence_chunk_ids', 'evidence_quotes_json', 'provenance_json'}
        self.assertLessEqual(stored, m.ALLOWED_PROPERTIES['Concept'])
        self.assertLessEqual({'relation_id', 'relation_ids'}, m.RELATIONSHIP_PROPERTIES)
        self.assertIn('attributions_and_notices', m.ALLOWED_PROPERTIES['Document'])
        # Vectors are stored on chunks but a generated query must never read them.
        self.assertNotIn('embedding', m.ALL_PROPERTIES)
        self.assertNotIn('extraction_method', m.ALL_PROPERTIES)

    def test_relationship_properties_are_readable(self):
        result = m.validate_cypher('MATCH (a:Concept)-[r:IS_A]->(b:Concept) '
                                   'RETURN r.relation_id AS id, r.relation_ids AS ids')
        self.assertEqual(result['properties'], ['relation_id', 'relation_ids'])

    def test_evidence_projection_can_be_disabled(self):
        query = m.compile_plan(plan(include_evidence=False))['cypher']
        self.assertIn('relationship_types', query)
        self.assertNotIn('evidence_quotes_json', query)

    def test_rejects_unknown_label_and_bad_identifier(self):
        with self.assertRaises(m.InvalidPlan):
            m.compile_plan(plan(start={'label': 'Secret', 'id': 'C_x'}))
        with self.assertRaises(m.InvalidPlan):
            m.compile_plan(plan(start={'label': 'Concept', 'id': 'C_Not Valid'}))

    def test_rejects_injection_through_relationship_types(self):
        hops = [{'direction': 'out', 'types': ['IS_A]->(x) DELETE x'], 'target_label': 'Concept'}]
        with self.assertRaises(m.InvalidPlan):
            m.compile_plan(plan(hops=hops))

    def test_rejects_hop_budget_violations(self):
        hop = {'direction': 'out', 'types': ['IS_A'], 'target_label': 'Concept'}
        with self.assertRaises(m.InvalidPlan):
            m.compile_plan(plan(hops=[hop] * 5), max_hops=3)
        with self.assertRaises(m.InvalidPlan):
            m.compile_plan(plan(hops=[]))

    def test_rejects_malformed_hops_and_limits(self):
        with self.assertRaises(m.InvalidPlan):
            m.compile_plan(plan(hops=[{'direction': 'sideways', 'types': ['IS_A'],
                                       'target_label': 'Concept'}]))
        with self.assertRaises(m.InvalidPlan):
            m.compile_plan(plan(hops=[{'direction': 'out', 'types': ['IS_A', 'IS_A'],
                                       'target_label': 'Concept'}]))
        with self.assertRaises(m.InvalidPlan):
            m.compile_plan(plan(hops=[{'direction': 'out', 'types': ['IS_A', 'SUPPORTS',
                                                                     'GOVERNS', 'REQUIRES'],
                                       'target_label': 'Concept'}]))
        with self.assertRaises(m.InvalidPlan):
            m.compile_plan(plan(limit=True))
        with self.assertRaises(m.InvalidPlan):
            m.compile_plan(plan(limit=5000))
        with self.assertRaises(m.InvalidPlan):
            m.compile_plan(plan(extra='ignored'))


class RejectUnsafeCypherTests(unittest.TestCase):
    def assertRejected(self, query, fragment, parameters=None):
        with self.assertRaises(m.UnsafeCypher) as caught:
            m.validate_cypher(query, parameters)
        self.assertIn(fragment, str(caught.exception))

    def test_rejects_writes(self):
        for clause in ('DELETE n', 'DETACH DELETE n', 'SET n.x = 1', 'REMOVE n.x'):
            self.assertRejected(f'MATCH (n:Concept) RETURN n {clause}', 'Forbidden clause')
        self.assertRejected('CREATE (n:Concept) RETURN n', 'Forbidden clause')
        self.assertRejected('MERGE (n:Concept) RETURN n', 'Forbidden clause')

    def test_rejects_procedures_and_imports(self):
        self.assertRejected('CALL apoc.export.json.all("out.json") RETURN 1', 'Forbidden clause')
        self.assertRejected('LOAD CSV FROM "http://x" AS row RETURN row', 'Forbidden clause')

    def test_rejects_second_statement(self):
        self.assertRejected('MATCH (n:Concept) RETURN n; MATCH (m:Chunk) DELETE m', 'one statement')

    def test_rejects_comments_literals_and_quoted_identifiers(self):
        self.assertRejected('MATCH (n:Concept) RETURN n // harmless', 'Comments')
        self.assertRejected('MATCH (n:Concept) RETURN n /* x */', 'Comments')
        self.assertRejected("MATCH (n:Concept {canonical_name: 'foreign key'}) RETURN n", 'String literals')
        self.assertRejected('MATCH (n:Concept) RETURN n.`text`', 'Quoted identifiers')

    def test_rejects_schema_outside_the_contract(self):
        self.assertRejected('MATCH (n:Secret) RETURN n', 'Unknown label')
        self.assertRejected('MATCH ()-[r:HACKS]->() RETURN r', 'Unknown relationship type')
        self.assertRejected('MATCH (n:Concept) RETURN n.password', 'Unknown property')
        self.assertRejected('MATCH (n:Concept) RETURN n.name', 'Unknown property')

    def test_rejects_untyped_relationship_patterns(self):
        self.assertRejected('MATCH (a:Concept)-[r]-(b:Concept) RETURN r',
                            'must declare an allowed type')
        self.assertRejected('MATCH (a:Concept)--(b:Concept) RETURN a',
                            'must declare an allowed type')

    def test_rejects_queries_without_match_or_return(self):
        self.assertRejected('RETURN 1', 'must contain a MATCH')
        self.assertRejected('MATCH (n:Concept)', 'must contain a RETURN')

    def test_rejects_unbounded_and_deep_traversal(self):
        for query in ('MATCH p=(a:Concept)-[r:IS_A*]->(b:Concept) RETURN p',
                      'MATCH p=(a:Concept)-[r:IS_A*1..]->(b:Concept) RETURN p'):
            self.assertRejected(query, 'explicit upper bound')
        self.assertRejected('MATCH p=(a:Concept)-[r:IS_A*1..99]->(b:Concept) RETURN p', 'hop budget')
        self.assertRejected('MATCH p=(a:Concept)-[:IS_A]-(b:Concept)-[:IS_A]-(c:Concept)'
                            '-[:IS_A]-(d:Concept)-[:IS_A]-(e:Concept)-[:IS_A]-(f:Concept) RETURN p',
                            'relationship patterns')

    def test_rejects_oversized_limit_and_missing_parameters(self):
        self.assertRejected('MATCH (n:Concept) RETURN n LIMIT 100000', 'LIMIT must be between')
        self.assertRejected('MATCH (n:Concept) RETURN n LIMIT 0', 'LIMIT must be between')
        self.assertRejected('MATCH (n:Concept {concept_id: $}) RETURN n', 'Unsupported character')


class AcceptSafeCypherTests(unittest.TestCase):
    def test_accepts_parameterised_read_only_queries(self):
        result = m.validate_cypher(
            'MATCH (c:Concept {concept_id: $id}) RETURN c.name_pt AS name, c.aliases AS aliases',
            {'id': 'C_join'})
        self.assertEqual(result['labels'], ['Concept'])
        self.assertEqual(result['properties'], ['aliases', 'name_pt'])
        self.assertEqual(result['required_parameters'], ['id', 'limit'])
        self.assertTrue(result['limit_injected'])
        self.assertEqual(result['parameters']['limit'], 25)

    def test_accepts_projection_maps_and_list_comprehensions(self):
        result = m.validate_cypher(
            'MATCH (d:Document)-[:CONTAINS]->(c:Chunk) '
            'RETURN d.title AS title, collect({chunk: c.chunk_id, words: c.word_count}) AS chunks LIMIT 5')
        self.assertEqual(result['relationship_types'], ['CONTAINS'])
        self.assertEqual(result['limit'], 5)
        self.assertFalse(result['limit_injected'])
        self.assertEqual(result['relationship_patterns'], 1)

    def test_accepts_bounded_variable_length_and_parameter_limit(self):
        result = m.validate_cypher(
            'MATCH (a:Concept)-[r:IS_A|SUPPORTS*1..2]->(b:Concept) RETURN a, b LIMIT $limit',
            {'limit': 5})
        self.assertEqual(result['relationship_patterns'], 1)
        self.assertEqual(result['limit'], 5)
        self.assertFalse(result['limit_injected'])

    def test_given_parameters_must_cover_the_query(self):
        with self.assertRaises(m.UnsafeCypher) as caught:
            m.validate_cypher('MATCH (c:Concept {concept_id: $id}) RETURN c', {})
        self.assertIn('Missing parameter', str(caught.exception))

    def test_unused_parameters_are_reported_not_silently_dropped(self):
        result = m.validate_cypher('MATCH (c:Concept {concept_id: $id}) RETURN c',
                                   {'id': 'C_join', 'unused': 1})
        self.assertEqual(result['unused_parameters'], ['unused'])


if __name__ == '__main__':
    unittest.main()
