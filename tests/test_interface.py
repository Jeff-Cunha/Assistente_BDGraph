"""Interface fixtures: the planner rules and the HTTP contract.

No test here needs Neo4j or the model: the graph is replaced by a fixed catalog and the
answer by a recorded one, so a broken screen is caught without waiting two minutes.
"""
import contextlib
from pathlib import Path
import sys
import time
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient           # noqa: E402

from app import engine, interface, planner          # noqa: E402

CATALOG = [
    {'id': 'C_key', 'name_pt': 'chave', 'canonical_name': 'key'},
    {'id': 'C_primary_key', 'name_pt': 'chave primária', 'canonical_name': 'primary key'},
    {'id': 'C_foreign_key', 'name_pt': 'chave estrangeira', 'canonical_name': 'foreign key'},
    {'id': 'C_referential_integrity', 'name_pt': 'integridade referencial',
     'canonical_name': 'referential integrity'},
    {'id': 'C_join', 'name_pt': 'junção', 'canonical_name': 'join'},
]

ANSWER = {
    'schema_version': '0.1.0',
    'question': 'O que é chave primária?',
    'answered': True,
    'answer_pt': 'A chave primária identifica uma linha de forma única.',
    'claims': [{'text': 'Identifica a linha.', 'evidence_ids': ['E1']}],
    'dropped_claims': [],
    'citations': [{'evidence_id': 'E1', 'chunk_id': 'D03_C001', 'document_id': 'D03',
                   'title': 'Chapter 9', 'quote': 'A primary key', 'section_path': []}],
    'sources': [{'document_id': 'D03', 'title': 'Chapter 9', 'chunk_ids': ['D03_C001'],
                 'source_url': 'https://example.invalid/d03'}],
    'support': {'level': 'high', 'coverage': 1.0, 'claims_with_evidence': 1,
                'claims_without_evidence': 0, 'distinct_chunks': 1, 'distinct_documents': 1,
                'unverified_quotes': 0, 'reasons': ['1 de 1 afirmação cita evidência.']},
    'limitations': [],
    'graph': {'cypher': 'MATCH (n0:Concept) RETURN n0 LIMIT $limit',
              'parameters': {'id_0': 'C_primary_key', 'limit': 12},
              'paths': [{'nodes': [{'label': 'Concept', 'id': 'C_primary_key',
                                    'name': 'chave primária'},
                                   {'label': 'Concept', 'id': 'C_key', 'name': 'chave'}],
                         'relationships': [{'type': 'IS_A', 'relation_id': 'R1',
                                            'evidence_quotes_json':
                                            '[{"chunk_id": "D03_C001", "quote": "A primary key"}]'}]}]},
    'model': {'provider': 'ollama_local', 'model': 'qwen3:8b'},
    'reading': {'strategy': 'shortest-path', 'explanation': 'Caminho de 1 salto.'},
    'plan': {'start': {'label': 'Concept', 'id': 'C_primary_key'},
             'hops': [{'direction': 'out', 'types': ['IS_A'], 'target_label': 'Concept'}],
             'limit': 12},
}


class RankingTest(unittest.TestCase):
    def test_specific_phrase_beats_the_bare_word(self):
        ranked = planner.rank_concepts('O que é chave primária?', CATALOG)
        self.assertEqual(ranked[0]['id'], 'C_primary_key')

    def test_plural_and_accents_do_not_hide_a_concept(self):
        ranked = planner.rank_concepts('Quais relacoes ligam chaves estrangeiras?', CATALOG)
        self.assertEqual(ranked[0]['id'], 'C_foreign_key')

    def test_question_outside_the_graph_matches_nothing(self):
        self.assertEqual(planner.rank_concepts('Como faço um bolo de cenoura?', CATALOG), [])

    def test_unknown_question_lists_suggestions(self):
        self.assertEqual(planner.PlanError('x', ['a']).suggestions, ['a'])


class QuoteTest(unittest.TestCase):
    TEXT = ('Uma chave primária identifica a linha. Uma chave estrangeira aponta '
            'para outra tabela.')

    def test_quote_is_a_literal_slice(self):
        quote = engine.extract_quote(self.TEXT, ['chave estrangeira'])
        self.assertIn(quote, self.TEXT)
        self.assertTrue(quote.startswith('Uma chave estrangeira'))

    def test_accent_insensitive_match_keeps_the_original_text(self):
        quote = engine.extract_quote('A juncao externa preserva as linhas. Nada mais.',
                                     ['junção externa'])
        self.assertTrue(quote.startswith('A juncao externa'))

    def test_no_match_returns_empty(self):
        self.assertEqual(engine.extract_quote(self.TEXT, ['transação']), '')


class FallbackPlanTest(unittest.TestCase):
    def test_text_plan_is_accepted_by_the_guard(self):
        plan = planner.text_plan('C_primary_key')
        compiled = engine.guard.compile_plan(plan, max_hops=3)
        self.assertIn('MENTIONS', compiled['cypher'])
        self.assertFalse(plan['include_evidence'])

    def test_text_plan_refuses_an_identifier_outside_the_contract(self):
        with self.assertRaises(engine.guard.InvalidPlan):
            planner.text_plan('primary key; DROP')


class InterfaceTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(interface.app)
        interface.JOBS.clear()

    def test_index_is_served(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Dossiê', response.text)

    def test_short_question_is_refused(self):
        self.assertEqual(self.client.post('/api/ask', json={'question': 'a'}).status_code, 422)

    def test_missing_job_is_404(self):
        self.assertEqual(self.client.get('/api/job/nao-existe').status_code, 404)

    def test_answer_reaches_the_job(self):
        with unittest.mock.patch.object(engine, 'answer_question', return_value=dict(ANSWER)), \
             unittest.mock.patch.object(engine, 'save_run', return_value=Path('x')):
            created = self.client.post('/api/ask', json={'question': 'O que é chave primária?',
                                                         'model': 'qwen3:8b'})
            self.assertEqual(created.status_code, 200)
            job_id = created.json()['job_id']
            record = self._wait(job_id)
        self.assertEqual(record['status'], 'done')
        self.assertEqual(record['answer']['support']['level'], 'high')
        self.assertEqual(record['answer']['graph']['paths'][0]['relationships'][0]['type'], 'IS_A')

    def test_unmatched_question_keeps_the_suggestions(self):
        def refuse(*args, **kwargs):
            raise planner.PlanError('nada no grafo', ['chave primária', 'junção'])

        with unittest.mock.patch.object(engine, 'answer_question', side_effect=refuse):
            job_id = self.client.post('/api/ask', json={'question': 'receita de bolo'}).json()['job_id']
            record = self._wait(job_id)
        self.assertEqual(record['status'], 'unmatched')
        self.assertEqual(record['suggestions'], ['chave primária', 'junção'])

    def test_a_model_failure_is_reported_not_hidden(self):
        def explode(*args, **kwargs):
            raise engine.EngineError('O Ollama não respondeu; verifique se está rodando.')

        with unittest.mock.patch.object(engine, 'answer_question', side_effect=explode):
            job_id = self.client.post('/api/ask', json={'question': 'O que é junção?'}).json()['job_id']
            record = self._wait(job_id)
        self.assertEqual(record['status'], 'error')
        self.assertIn('Ollama', record['message'])

    def test_health_reports_both_services(self):
        report = {'neo4j': {'online': True, 'nodes': {'Concept': 93}},
                  'ollama': {'online': True, 'models': [{'name': 'qwen3:8b'}]}}
        with unittest.mock.patch.object(engine, 'health', return_value=report), \
             unittest.mock.patch.object(engine, 'ollama_status',
                                        return_value={'online': True, 'models': [{'name': 'qwen3:8b'}]}):
            body = self.client.get('/api/health').json()
        self.assertTrue(body['neo4j']['online'])
        self.assertEqual(body['model_default'], 'qwen3:8b')

    def test_suggestions_use_the_graph_vocabulary(self):
        @contextlib.contextmanager
        def fake_database():
            yield (None, 'neo4j')

        with unittest.mock.patch.object(engine, 'database', fake_database), \
             unittest.mock.patch.object(engine, 'concepts', return_value=CATALOG):
            body = self.client.get('/api/suggest', params={'q': 'chave prim'}).json()
        self.assertEqual(body['suggestions'][0]['id'], 'C_primary_key')

    def _wait(self, job_id, timeout=6.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            record = self.client.get(f'/api/job/{job_id}').json()
            if record['status'] not in ('queued', 'running'):
                return record
            time.sleep(0.05)
        self.fail('job did not finish in time')


if __name__ == '__main__':
    unittest.main()
