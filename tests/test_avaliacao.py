"""O gabarito da avaliação tem de apontar para o que existe no grafo e no corpus.

Um erro de digitação em `perguntas.jsonl` produziria uma rodada inteira marcada como errada sem
que ninguém percebesse, então os identificadores são conferidos contra os dados reais.
"""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import engine                                   # noqa: E402

QUESTIONS = ROOT / 'data' / 'avaliacao' / 'perguntas.jsonl'
spec = importlib.util.spec_from_file_location('run_avaliacao', ROOT / 'scripts' / 'run-avaliacao.py')
avaliacao = importlib.util.module_from_spec(spec)
spec.loader.exec_module(avaliacao)


def corpus_documents():
    documents = set()
    for name in ('chunks.jsonl', 'figure_supplements.jsonl'):
        path = ROOT / 'corpus' / 'chunks' / name
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                documents.add(json.loads(line)['document_id'])
    return documents


def graph_concepts():
    module = engine._load('retrieval_parte3', 'retrieval.py')
    concepts, relations, _ = module.load_graph_data(ROOT, include_sample=True)
    return set(concepts), len(relations)


class QuestionSetTest(unittest.TestCase):
    def setUp(self):
        self.questions = avaliacao.load_questions(QUESTIONS)

    def test_fifteen_questions_in_three_groups(self):
        self.assertEqual(len(self.questions), 15)
        kinds = {}
        for question in self.questions:
            kinds[question['tipo']] = kinds.get(question['tipo'], 0) + 1
        self.assertEqual(kinds, {'multihop': 5, 'conceitual': 5, 'sem-resposta': 5})

    def test_identifiers_are_unique_and_the_text_is_not_empty(self):
        identifiers = [question['id'] for question in self.questions]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        for question in self.questions:
            self.assertTrue(question['pergunta'].strip())

    def test_expected_concepts_exist_in_the_graph(self):
        concepts, _ = graph_concepts()
        for question in self.questions:
            for concept in question['conceitos']:
                with self.subTest(question=question['id'], concept=concept):
                    self.assertIn(concept, concepts)

    def test_expected_documents_exist_in_the_corpus(self):
        documents = corpus_documents()
        for question in self.questions:
            for document in question['documentos']:
                with self.subTest(question=question['id'], document=document):
                    self.assertIn(document, documents)

    def test_questions_with_an_answer_have_an_expected_document(self):
        for question in self.questions:
            if question['espera_resposta']:
                with self.subTest(question=question['id']):
                    self.assertTrue(question['documentos'])
                    self.assertTrue(question['conceitos'])
            else:
                with self.subTest(question=question['id']):
                    self.assertFalse(question['documentos'])

    def test_multihop_questions_use_relations_that_exist(self):
        module = engine._load('retrieval_parte3', 'retrieval.py')
        _, relations, _ = module.load_graph_data(ROOT, include_sample=True)
        neighbours = {}
        for relation in relations:
            neighbours.setdefault(relation['source'], set()).add(relation['target'])
        for question in self.questions:
            if question['tipo'] != 'multihop':
                continue
            path = question['conceitos']
            with self.subTest(question=question['id']):
                for source, target in zip(path, path[1:]):
                    self.assertIn(target, neighbours.get(source, set()),
                                  f'{source} não alcança {target} em um salto')


def answer(answered=True, level='high', documents=('D03',), unverified=0, claims=2):
    return {
        'answered': answered,
        'claims': [{'text': 'x', 'evidence_ids': ['E1']}] * claims,
        'citations': [{'evidence_id': f'E{i}', 'document_id': document, 'chunk_id': f'{document}_C001'}
                      for i, document in enumerate(documents, 1)],
        'support': {'level': level, 'coverage': 1.0, 'unverified_quotes': unverified},
    }


class MeasureTest(unittest.TestCase):
    question = {'id': 'Q1', 'tipo': 'conceitual', 'documentos': ['D03'], 'espera_resposta': True}
    missing = {'id': 'Q9', 'tipo': 'sem-resposta', 'documentos': [], 'espera_resposta': False}

    def test_correct_when_the_expected_document_is_cited(self):
        row = avaliacao.measure(self.question, answer(), 'hybrid', 10.0)
        self.assertEqual(row['correta'], 'sim')
        self.assertEqual(row['documentos_citados'], 'D03')

    def test_wrong_when_another_document_is_cited(self):
        row = avaliacao.measure(self.question, answer(documents=('D07',)), 'vector', 10.0)
        self.assertEqual(row['correta'], 'não')
        self.assertIn('documento esperado ausente', row['observacao'])

    def test_wrong_when_the_quote_is_not_verified(self):
        row = avaliacao.measure(self.question, answer(unverified=2), 'hybrid', 10.0)
        self.assertEqual(row['correta'], 'não')
        self.assertIn('não verificada', row['observacao'])

    def test_abstention_counts_as_correct_only_where_nothing_is_expected(self):
        self.assertEqual(avaliacao.measure(self.missing, answer(answered=False), 'hybrid', 5.0)['correta'], 'sim')
        self.assertEqual(avaliacao.measure(self.missing, answer(answered=True), 'hybrid', 5.0)['correta'], 'não')
        self.assertEqual(avaliacao.measure(self.question, answer(answered=False), 'hybrid', 5.0)['correta'], 'não')

    def test_summary_counts_every_mode(self):
        rows = [avaliacao.measure(self.question, answer(), mode, 10.0)
                for mode in ('vector', 'hybrid', 'graph')]
        table = avaliacao.summarise(rows)
        self.assertEqual([row['modo'] for row in table], ['vector', 'hybrid', 'graph'])
        self.assertTrue(all(row['corretas'] == 1 for row in table))


if __name__ == '__main__':
    unittest.main()
