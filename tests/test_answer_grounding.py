"""Synthetic bundles only; they exercise the rules, not the extraction quality."""
import importlib.util
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('answer_grounding', ROOT / 'scripts/answer-grounding.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SCHEMA = json.loads((ROOT / 'schemas/answer.schema.json').read_text(encoding='utf-8'))


def evidence(chunk_id='D03_C001', quote='Constraints are the rules', status='accepted',
             document='D03', evidence_id=None, origin='graph'):
    item = {'chunk_id': chunk_id, 'document_id': document, 'title': f'Document {document}',
            'source_url': f'https://example.org/{chunk_id}', 'section_path': ['Chapter'],
            'quote': quote, 'review_status': status, 'origin': origin}
    if evidence_id:
        item['evidence_id'] = evidence_id
    return item


def bundle(items=None, channels=('vector', 'graph')):
    return {
        'question': 'Como a integridade referencial se relaciona com a chave estrangeira?',
        'language': 'pt-BR',
        'retrieval': {'strategy': 'hybrid', 'channels': list(channels),
                      'graph_executed': 'graph' in channels, 'max_hops': 2},
        'concepts': [],
        'evidence': items if items is not None else [
            evidence(), evidence('D07_C001', 'Outer joins keep unmatched rows', document='D07')],
    }


def response(claims=None, answered=True, text='Resposta fundamentada.'):
    return {'answered': answered, 'answer_pt': text,
            'claims': claims if claims is not None else [{'text': 'a', 'evidence_ids': ['E1']}],
            'notes': ''}


class BundleTests(unittest.TestCase):
    def test_evidence_ids_are_assigned_in_input_order(self):
        normalized = m.normalize_bundle(bundle([evidence(), evidence('D07_C001', 'x', document='D07')]))
        self.assertEqual([item['evidence_id'] for item in normalized['evidence']], ['E1', 'E2'])
        self.assertEqual(normalized['retrieval']['channels'], ['vector', 'graph'])

    def test_rejects_malformed_or_duplicated_evidence(self):
        cases = [
            [evidence(chunk_id='X1')],
            [evidence(quote='   ')],
            [evidence(evidence_id='E1'), evidence(evidence_id='E1')],
            [evidence(evidence_id='Q1')],
            [evidence(status='approved')],
            [evidence(origin='web')],
        ]
        for items in cases:
            with self.assertRaises(m.GroundingError):
                m.normalize_bundle(bundle(items))

    def test_rejects_empty_evidence_so_the_caller_abstains_before_the_model(self):
        with self.assertRaises(m.GroundingError) as caught:
            m.normalize_bundle(bundle([]))
        self.assertIn('at least one evidence item', str(caught.exception))

    def test_rejects_invalid_channels(self):
        with self.assertRaises(m.GroundingError):
            m.normalize_bundle(bundle(channels=('semantic',)))


class VerificationTests(unittest.TestCase):
    def test_rejects_invented_citation(self):
        with self.assertRaises(m.GroundingError) as caught:
            m.verify_model_answer(response([{'text': 'a', 'evidence_ids': ['E9']}]),
                                  m.normalize_bundle(bundle()))
        self.assertIn('outside the bundle', str(caught.exception))

    def test_rejects_fields_the_contract_does_not_allow(self):
        raw = response()
        raw['confidence'] = 0.93
        with self.assertRaises(m.GroundingError) as caught:
            m.verify_model_answer(raw, m.normalize_bundle(bundle()))
        self.assertIn('Unexpected field', str(caught.exception))

    def test_claim_without_evidence_is_set_aside_not_used(self):
        raw = response([{'text': 'afirmação solta', 'evidence_ids': []},
                        {'text': 'com fonte', 'evidence_ids': ['E1']}])
        verified = m.verify_model_answer(raw, m.normalize_bundle(bundle()))
        self.assertEqual(len(verified['kept']), 1)
        self.assertEqual(verified['dropped'][0]['reason'], 'claim_without_evidence')

    def test_abstention_carrying_claims_is_rejected(self):
        with self.assertRaises(m.GroundingError):
            m.verify_model_answer(response(answered=False), m.normalize_bundle(bundle()))


class ResponseTests(unittest.TestCase):
    def build(self, raw=None, items=None, chunk_texts=None, channels=('vector', 'graph')):
        return m.evaluate(bundle(items, channels), raw if raw is not None else response(),
                          chunk_texts)

    def test_single_chunk_answer_is_medium_and_validates(self):
        result = self.build()
        self.assertTrue(result['answered'])
        self.assertEqual(result['support']['level'], 'medium')
        self.assertEqual(result['support']['coverage'], 1.0)
        self.assertEqual([c['chunk_id'] for c in result['citations']], ['D03_C001'])
        Draft202012Validator(SCHEMA).validate(result)

    def test_two_claims_over_two_documents_reach_high_and_list_both_sources(self):
        result = self.build(response([{'text': 'a', 'evidence_ids': ['E1']},
                                      {'text': 'b', 'evidence_ids': ['E2']}]))
        self.assertEqual(result['support']['level'], 'high')
        self.assertEqual(result['support']['distinct_documents'], 2)
        self.assertEqual([s['document_id'] for s in result['sources']], ['D03', 'D07'])
        Draft202012Validator(SCHEMA).validate(result)

    def test_single_document_is_medium_with_a_stated_limitation(self):
        items = [evidence(), evidence('D03_C002', 'Another passage')]
        result = self.build(response([{'text': 'a', 'evidence_ids': ['E1']},
                                      {'text': 'b', 'evidence_ids': ['E2']}]), items=items)
        self.assertEqual(result['support']['level'], 'medium')
        self.assertTrue(any('único documento' in text for text in result['limitations']))

    def test_flagged_evidence_is_low(self):
        result = self.build(items=[evidence(status='flagged')])
        self.assertEqual(result['support']['level'], 'low')
        self.assertTrue(any('sinalizada' in text for text in result['support']['reasons']))

    def test_unverified_quote_caps_at_medium(self):
        result = self.build(chunk_texts={'D03_C001': 'texto sem a citação'})
        self.assertFalse(result['citations'][0]['quote_verified'])
        self.assertEqual(result['support']['level'], 'medium')
        self.assertEqual(result['support']['unverified_quotes'], 1)

    def test_quote_with_markdown_escape_still_verifies(self):
        items = [evidence(quote='range \\[Jan 1, 1950, Jan 1, 2000\\]'),
                 evidence('D07_C001', 'Outer joins keep unmatched rows', document='D07')]
        result = self.build(response([{'text': 'a', 'evidence_ids': ['E1']}]), items=items,
                            chunk_texts={'D03_C001': 'range [Jan 1, 1950, Jan 1, 2000]'})
        self.assertTrue(result['citations'][0]['quote_verified'])

    def test_model_abstention_uses_the_project_sentence(self):
        result = self.build(response(answered=False, text='Não sei responder.', claims=[]))
        self.assertFalse(result['answered'])
        self.assertEqual(result['answer_pt'], m.ABSTENTION_PT)
        self.assertEqual(result['support']['level'], 'insufficient')
        self.assertIn('Não sei responder.', result['support']['reasons'][0])
        self.assertEqual(result['citations'], [])
        Draft202012Validator(SCHEMA).validate(result)

    def test_all_claims_dropped_produces_an_abstention(self):
        result = self.build(response([{'text': 'solto', 'evidence_ids': []}]))
        self.assertFalse(result['answered'])
        self.assertEqual(result['support']['level'], 'insufficient')
        self.assertEqual(len(result['dropped_claims']), 1)
        Draft202012Validator(SCHEMA).validate(result)

    def test_missing_model_response_produces_an_abstention(self):
        result = m.evaluate(bundle(), None)
        self.assertFalse(result['answered'])
        self.assertEqual(result['support']['level'], 'insufficient')

    def test_vector_only_retrieval_states_that_no_graph_path_was_walked(self):
        result = self.build(channels=('vector',))
        self.assertTrue(any('Nenhum caminho do grafo' in text for text in result['limitations']))

    def test_evaluation_is_deterministic(self):
        self.assertEqual(self.build(), self.build())

    def test_graph_block_is_passed_through_for_the_interface(self):
        graph = {'cypher': 'MATCH (n0:Concept) RETURN n0 LIMIT $limit',
                 'parameters': {'id_0': 'C_join', 'limit': 5}}
        result = m.evaluate(bundle(), response(), None, graph=graph,
                            model={'provider': 'ollama_local', 'model': 'qwen3:8b'})
        self.assertEqual(result['graph'], graph)
        self.assertEqual(result['model']['model'], 'qwen3:8b')
        Draft202012Validator(SCHEMA).validate(result)


class CorpusQuoteTests(unittest.TestCase):
    def test_sample_quotes_match_the_stored_corpus_text(self):
        texts = m.load_corpus_texts()
        self.assertEqual(len(texts), 59)
        sample = json.loads((ROOT / 'data/extraction/sample.json').read_text(encoding='utf-8'))
        items = [{'chunk_id': ref['chunk_id'], 'document_id': ref['chunk_id'][:3],
                  'quote': ref['quote']}
                 for ref in (ref for concept in sample['concepts'] for ref in concept['evidence'])]
        checked = m.check_quotes(items, texts)
        self.assertEqual([item['quote_verified'] for item in checked],
                         [True] * len(checked))


if __name__ == '__main__':
    unittest.main()
