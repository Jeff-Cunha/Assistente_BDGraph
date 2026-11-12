"""Testes unitários e de integração do Mecanismo de Recuperação Híbrida (Pessoa 3 - Adijair)."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('retrieval', ROOT / 'scripts/retrieval.py')
retrieval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retrieval)


class RetrievalUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = retrieval.HybridRetriever(ROOT)

    def test_corpus_loading_counts(self):
        """Verifica se os 59 trechos (31 texto + 28 figuras) e documentos foram carregados."""
        chunks, texts, sources = self.retriever.chunks, self.retriever.texts, self.retriever.sources
        self.assertEqual(len(chunks), 59)
        self.assertEqual(len(texts), 59)
        self.assertEqual(len(sources), 9)

    def test_precomputed_embeddings_integrity(self):
        """Verifica se os embeddings pré-computados cobrem todos os 59 trechos com dimensão 384."""
        embs = self.retriever.precomputed_embeddings
        self.assertEqual(len(embs), 59)
        for cid, vec in embs.items():
            self.assertEqual(len(vec), 384, f"Dimensão incorreta para chunk {cid}")
            # Verifica se o vetor está normalizado (norma ~ 1.0)
            norm = sum(x * x for x in vec) ** 0.5
            self.assertAlmostEqual(norm, 1.0, places=3, msg=f"Vetor de {cid} não está normalizado")

    def test_concept_identification_accents_and_case(self):
        """Verifica identificação de conceitos ignorando maiúsculas e acentos."""
        q1 = "O que é uma chave estrangeira e como ela se relaciona com integridade referencial?"
        concepts = retrieval.identify_concepts(q1, self.retriever.concepts)
        c_ids = {c['concept_id'] for c in concepts}
        self.assertIn('C_foreign_key', c_ids)
        self.assertIn('C_referential_integrity', c_ids)

        q2 = "Explique JUNÇÃO externa a esquerda e GROUP BY"
        concepts2 = retrieval.identify_concepts(q2, self.retriever.concepts)
        c_ids2 = {c['concept_id'] for c in concepts2}
        self.assertTrue('C_join' in c_ids2 or 'C_left_outer_join' in c_ids2)
        self.assertIn('C_group_by', c_ids2)

    def test_shortest_path_graph_algorithm(self):
        """Algoritmo de Grafo: verifica busca de menor caminho entre integridade referencial e left outer join."""
        adj = {}
        for r in self.retriever.relations:
            src, tgt = r['source'], r['target']
            adj.setdefault(src, []).append((tgt, r))
            rev_r = dict(r)
            rev_r['_reversed'] = True
            adj.setdefault(tgt, []).append((src, rev_r))

        path_edges = retrieval.shortest_path(adj, 'C_referential_integrity', 'C_left_outer_join')
        self.assertIsNotNone(path_edges)
        self.assertTrue(len(path_edges) >= 2)
        # Confere que cada aresta conecta o nó anterior ao próximo
        curr = 'C_referential_integrity'
        for e in path_edges:
            if e['source'] == curr:
                curr = e['target']
            else:
                curr = e['source']
        self.assertEqual(curr, 'C_left_outer_join')

    def test_degree_centrality_graph_algorithm(self):
        """Algoritmo de Grafo: testa cálculo de centralidade de grau em subgrafo."""
        adj = {}
        candidate_nodes = {'C_foreign_key', 'C_join', 'C_primary_key', 'C_table'}
        for r in self.retriever.relations:
            src, tgt = r['source'], r['target']
            adj.setdefault(src, []).append((tgt, r))
            adj.setdefault(tgt, []).append((src, r))

        centrality = retrieval.calculate_degree_centrality(adj, candidate_nodes)
        self.assertEqual(set(centrality.keys()), candidate_nodes)
        for score in centrality.values():
            self.assertTrue(0.0 <= score <= 1.0)

    def test_reciprocal_rank_fusion(self):
        """Testa se RRF pontua mais alto chunks presentes em ambos os canais."""
        vec_results = [('D03_C001', 0.9), ('D01_C001', 0.8), ('D07_C001', 0.7)]
        graph_chunks = ['D07_C001', 'D02_C001']
        fused = retrieval.reciprocal_rank_fusion(vec_results, graph_chunks, k_rrf=60)
        top_cid = fused[0][0]
        # D03_C001 e D07_C001 devem estar nas primeiras posições
        fused_cids = [c for c, _ in fused]
        self.assertIn('D03_C001', fused_cids[:2])
        self.assertIn('D07_C001', fused_cids[:2])

    def test_quote_is_exact_substring(self):
        """Garante que qualquer citação gerada pelo extrator de quotes seja substring exata do texto."""
        for cid, text in list(self.retriever.texts.items())[:10]:
            quote = retrieval.find_best_quote(text, "integridade referencial chave primária")
            self.assertIn(quote, text, f"Quote não encontrada no chunk {cid}")
            self.assertTrue(len(quote) > 0)

    def test_retrieve_bundle_matches_contrato_llm(self):
        """Valida que o bundle gerado pelo retriever passa 100% no validador do contrato da Parte 4."""
        q = "Como a integridade referencial se relaciona com chaves estrangeiras?"
        bundle = self.retriever.retrieve(q, top_k=5, max_hops=4)

        # Valida estrutura geral
        self.assertEqual(bundle['question'], q)
        self.assertEqual(bundle['language'], 'pt-BR')
        self.assertEqual(bundle['retrieval']['strategy'], 'hybrid')
        self.assertEqual(bundle['retrieval']['dimension'], 384)
        self.assertTrue(bundle['retrieval']['graph_executed'])

        # Valida contra o validador estrito
        errors = retrieval.validate_retrieval_bundle(bundle, self.retriever.texts)
        self.assertEqual(errors, [], f"Erros encontrados na validação do bundle: {errors}")

        # Valida que há pelo menos uma evidência originada do grafo e com relação
        graph_evidences = [ev for ev in bundle['evidence'] if ev['origin'] == 'graph']
        self.assertTrue(len(graph_evidences) > 0, "Deveria haver pelo menos uma evidência originada do grafo")
        for ev in graph_evidences:
            self.assertIsNotNone(ev['relation'])
            self.assertIn('type', ev['relation'])
            self.assertIn('source', ev['relation'])
            self.assertIn('target', ev['relation'])

    def test_vector_index_replaces_the_in_memory_vectors(self):
        """Com sessão do Neo4j, a busca vetorial vem de `chunk_embedding` (o caminho do --neo4j)."""
        class FakeSession:
            def __init__(self):
                self.queries = []

            def run(self, query, **params):
                self.queries.append((query, params))
                return iter([{'chunk_id': 'D08_C001', 'score': 0.9},
                             {'chunk_id': 'D06_C001', 'score': 0.8}])

        session = FakeSession()
        bundle = self.retriever.retrieve('O que é uma função agregadora?', top_k=3,
                                         max_hops=4, session=session)
        self.assertIn('chunk_embedding', session.queries[0][0])
        self.assertEqual(session.queries[0][1]['k'], 6)      # top_k * 2, como no caminho em memória
        self.assertIn('D08_C001', [ev['chunk_id'] for ev in bundle['evidence']])

    def test_section_path_is_flat_list_of_strings(self):
        """Verifica que o campo section_path é sempre List[str], nunca lista aninhada."""
        bundle = self.retriever.retrieve("O que é um banco de dados?", top_k=5)
        for ev in bundle['evidence']:
            sp = ev['section_path']
            self.assertIsInstance(sp, list)
            for item in sp:
                self.assertIsInstance(item, str)


if __name__ == '__main__':
    unittest.main()
