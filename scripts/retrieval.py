#!/usr/bin/env python3
"""Mecanismo de Recuperação Híbrida (GraphRAG / KAG) - Pessoa 3 (Adijair).

Combina busca vetorial densa (embeddings multilíngues), busca estruturada em grafo
(Neo4j LPG / Concept matching), travessia multi-hop (>= 2 saltos), algoritmos de grafo
(Shortest Path e Degree Centrality) e fusão por Reciprocal Rank Fusion (RRF).

Produz pacotes de evidência validados e compatíveis com o contrato da Parte 4 (Jotapê).
Funciona tanto conectado a uma instância ativa do Neo4j quanto em modo autônomo/offline
usando os dados validados do corpus e da extração.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import unicodedata
import warnings
from collections import Counter, OrderedDict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Suprime avisos desnecessários do HuggingFace e PyTorch no terminal
warnings.filterwarnings('ignore')
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
logging.getLogger('huggingface_hub').setLevel(logging.ERROR)
logging.getLogger('sentence_transformers').setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[1]
CORPUS_CHUNKS = ROOT / 'corpus/chunks/chunks.jsonl'
CORPUS_FIGURES = ROOT / 'corpus/chunks/figure_supplements.jsonl'
SOURCES_FILE = ROOT / 'corpus/metadata/sources.json'
EMBEDDINGS_FILE = ROOT / 'data/retrieval/chunk_embeddings.json'
SCHEMA_FILE = ROOT / 'db/schema.cypher'

DEFAULT_MODEL = 'paraphrase-multilingual-MiniLM-L12-v2'
VECTOR_DIMENSION = 384
CHUNK_ID_RE = re.compile(r'^[A-Z0-9]+_[A-Z0-9_]+$')


def strip_accents(text: str) -> str:
    """Remove acentos e normaliza para minúsculas."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def load_json(path: Path) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    items = []
    if not path.exists():
        return items
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def load_corpus(root: Path = ROOT) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str], Dict[str, Dict[str, Any]]]:
    """Carrega todos os 59 chunks (31 páginas + 28 figuras) e metadados de fontes."""
    sources = {s['document_id']: s for s in load_json(root / 'corpus/metadata/sources.json')}
    pages = load_jsonl(root / 'corpus/chunks/chunks.jsonl')
    figures = load_jsonl(root / 'corpus/chunks/figure_supplements.jsonl')

    chunks: Dict[str, Dict[str, Any]] = OrderedDict()
    texts: Dict[str, str] = {}

    for record in pages:
        cid = record['chunk_id']
        record['content_type'] = 'page_text'
        chunks[cid] = record
        texts[cid] = record['text']

    for record in figures:
        cid = record['chunk_id']
        record['content_type'] = 'figure_transcription'
        chunks[cid] = record
        texts[cid] = record['text']

    return chunks, texts, sources


def load_graph_data(root: Path = ROOT, include_sample: bool = True) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], Dict[str, Set[str]]]:
    """Carrega conceitos, relações semânticas e mapeamento Chunk -> Concepts a partir dos dados do projeto."""
    extractions = []
    # Diretórios padrão de extração
    dirs = [
        root / 'data/extraction/rule-knowledge-union-v2/extraction.json',
        root / 'data/extraction/model-knowledge-union-v3/extraction.json',
        root / 'data/extraction/manual-source-review-v1/extraction.json',
    ]
    if include_sample:
        dirs.append(root / 'data/extraction/sample.json')

    concepts: Dict[str, Dict[str, Any]] = {}
    relations: List[Dict[str, Any]] = []
    chunk_mentions: Dict[str, Set[str]] = OrderedDict()

    for p in dirs:
        if not p.exists():
            continue
        data = load_json(p)
        for c in data.get('concepts', []):
            cid = c['concept_id']
            if cid not in concepts:
                concepts[cid] = {
                    'concept_id': cid,
                    'canonical_name': c.get('canonical_name', ''),
                    'name_pt': c.get('name_pt', ''),
                    'category': c.get('category', 'general'),
                    'aliases': c.get('aliases', []),
                    'description_pt': c.get('description_pt', ''),
                    'evidence': c.get('evidence', [])
                }
            else:
                for a in c.get('aliases', []):
                    if a not in concepts[cid]['aliases']:
                        concepts[cid]['aliases'].append(a)
            for ev in c.get('evidence', []):
                chunk_mentions.setdefault(ev['chunk_id'], set()).add(cid)

        for r in data.get('relations', []):
            # Normaliza campos de evidência da relação
            rel_copy = dict(r)
            if 'evidence' in rel_copy and isinstance(rel_copy['evidence'], list):
                rel_copy['evidence_chunk_ids'] = [e['chunk_id'] for e in rel_copy['evidence'] if 'chunk_id' in e]
                rel_copy['evidence_quotes'] = [e.get('quote') for e in rel_copy['evidence'] if e.get('quote')]
                if rel_copy['evidence_quotes']:
                    rel_copy['evidence_quote'] = rel_copy['evidence_quotes'][0]
            relations.append(rel_copy)

    # Dedup relations by (source, type, target)
    seen_rel = {}
    for r in relations:
        key = (r['source'], r['type'], r['target'])
        if key not in seen_rel:
            seen_rel[key] = r
        else:
            # merge evidence chunk ids
            merged_ids = list(set(seen_rel[key].get('evidence_chunk_ids', []) + r.get('evidence_chunk_ids', [])))
            seen_rel[key]['evidence_chunk_ids'] = merged_ids

    return concepts, list(seen_rel.values()), chunk_mentions


class DenseEmbedder:
    """Gera e gerencia vetores densos usando SentenceTransformers."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: List[str] | str) -> Any:
        import numpy as np
        if isinstance(texts, str):
            texts = [texts]
        vecs = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.array(vecs, dtype=np.float32)


def cosine_similarity(v1: Any, v2: Any) -> float:
    """Produto escalar para vetores já L2-normalizados."""
    import numpy as np
    return float(np.dot(v1, v2))


def vector_search(query_vec: Any, chunk_embeddings: Dict[str, List[float]], top_k: int = 5) -> List[Tuple[str, float]]:
    """Busca por similaridade de cosseno em memória."""
    import numpy as np
    results = []
    q = np.array(query_vec, dtype=np.float32)
    norm = np.linalg.norm(q)
    if norm > 0:
        q = q / norm

    for cid, emb in chunk_embeddings.items():
        v = np.array(emb, dtype=np.float32)
        score = float(np.dot(q, v))
        results.append((cid, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


def identify_concepts(query: str, concepts: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identifica nós de conceitos na consulta do usuário através de casamento léxico insensível a acentos."""
    norm_query = strip_accents(query)
    # Tokenização básica para evitar casamentos parciais espúrios
    tokens = set(re.findall(r'\b\w+\b', norm_query))
    matched = []

    for cid, c in concepts.items():
        canonical = strip_accents(c['canonical_name'])
        name_pt = strip_accents(c['name_pt'])
        aliases = [strip_accents(a) for a in c.get('aliases', [])]

        candidate_terms = [canonical, name_pt] + aliases
        hit = False
        hit_term = ''
        for term in candidate_terms:
            if not term:
                continue
            # Verifica correspondência exata de frase ou termo
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, norm_query):
                hit = True
                hit_term = term
                break

        if hit:
            matched.append((len(hit_term), c))

    # Ordena pelos casamentos mais específicos (frases mais longas primeiro)
    matched.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in matched]


def shortest_path(graph_adj: Dict[str, List[Tuple[str, Dict[str, Any]]]], start_id: str, target_id: str) -> Optional[List[Dict[str, Any]]]:
    """Algoritmo de Grafo: Menor Caminho (Shortest Path / BFS) entre dois conceitos no grafo semântico."""
    if start_id == target_id:
        return []
    queue = deque([[start_id]])
    visited = {start_id}
    parent_edge: Dict[Tuple[str, str], Dict[str, Any]] = {}

    while queue:
        path = queue.popleft()
        current = path[-1]
        if current == target_id:
            # reconstrói a sequência de relações
            edges = []
            for u, v in zip(path[:-1], path[1:]):
                edges.append(parent_edge[(u, v)])
            return edges

        for neighbor, rel in graph_adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                parent_edge[(current, neighbor)] = rel
                queue.append(path + [neighbor])
    return None


def calculate_degree_centrality(graph_adj: Dict[str, List[Tuple[str, Dict[str, Any]]]], candidate_nodes: Set[str]) -> Dict[str, float]:
    """Algoritmo de Grafo: Centralidade de Grau para pontuar conceitos mais conectados no subgrafo."""
    degrees = {}
    for node in candidate_nodes:
        deg = len([n for n, _ in graph_adj.get(node, []) if n in candidate_nodes])
        degrees[node] = float(deg)
    max_deg = max(degrees.values()) if degrees and max(degrees.values()) > 0 else 1.0
    return {node: deg / max_deg for node, deg in degrees.items()}


def traverse_graph(seed_concepts: List[Dict[str, Any]], relations: List[Dict[str, Any]], max_hops: int = 4) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Realiza travessia multi-hop e computa menor caminho entre múltiplos conceitos sementes."""
    # Constrói adjacência direcionada e não direcionada para navegação
    adj: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for r in relations:
        src, tgt = r['source'], r['target']
        adj.setdefault(src, []).append((tgt, r))
        # aresta reversa para navegação bidirecional se necessário
        rev_r = dict(r)
        rev_r['_reversed'] = True
        adj.setdefault(tgt, []).append((src, rev_r))

    traversed_edges: List[Dict[str, Any]] = []
    seen_relations = set()

    seed_ids = [c['concept_id'] for c in seed_concepts]

    # 1. Se houver pelo menos 2 conceitos na pergunta, aplica Shortest Path entre pares
    if len(seed_ids) >= 2:
        for i in range(len(seed_ids)):
            for j in range(i + 1, len(seed_ids)):
                s, t = seed_ids[i], seed_ids[j]
                sp_edges = shortest_path(adj, s, t)
                if sp_edges:
                    for e in sp_edges:
                        rid = e.get('relation_id') or (e['source'], e['type'], e['target'])
                        if rid not in seen_relations:
                            seen_relations.add(rid)
                            traversed_edges.append(e)

    # 2. Travessia por vizinhança até max_hops a partir das sementes
    for seed in seed_ids:
        visited = {seed}
        q = deque([(seed, 0)])
        while q:
            curr, depth = q.popleft()
            if depth >= max_hops:
                continue
            for nxt, rel in adj.get(curr, []):
                rid = rel.get('relation_id') or (rel['source'], rel['type'], rel['target'])
                if rid not in seen_relations:
                    seen_relations.add(rid)
                    traversed_edges.append(rel)
                if nxt not in visited and depth + 1 < max_hops:
                    visited.add(nxt)
                    q.append((nxt, depth + 1))

    # Coleta todos os nós tocados pelas arestas
    touched_concept_ids = set(seed_ids)
    for e in traversed_edges:
        touched_concept_ids.add(e['source'])
        touched_concept_ids.add(e['target'])

    return traversed_edges, list(touched_concept_ids)


def format_section_path(record: Dict[str, Any], default_title: str) -> List[str]:
    """Garante que section_path seja sempre uma lista unidimensional de strings."""
    paths = record.get('section_paths') or record.get('section_path')
    if not paths:
        return [default_title]
    if isinstance(paths, list):
        if paths and isinstance(paths[0], list):
            return [str(p) for p in paths[0]]
        return [str(p) for p in paths]
    return [str(paths)]


def reciprocal_rank_fusion(vector_results: List[Tuple[str, float]], graph_chunk_ids: List[str], k_rrf: int = 60) -> List[Tuple[str, float]]:
    """Combina ranking vetorial e ranking estrutural do grafo com Reciprocal Rank Fusion."""
    rrf_scores: Dict[str, float] = Counter()

    for rank, (cid, _) in enumerate(vector_results, 1):
        rrf_scores[cid] += 1.0 / (k_rrf + rank)

    for rank, cid in enumerate(graph_chunk_ids, 1):
        rrf_scores[cid] += 1.0 / (k_rrf + rank)

    sorted_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_chunks


def find_best_quote(chunk_text: str, query: str) -> str:
    """Extrai uma sentença/citação literal representativa de chunk_text (garante quote in chunk_text)."""
    # Separa em frases por pontuação simples preservando integridade
    sentences = re.split(r'(?<=[.!?])\s+', chunk_text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    if not sentences:
        return chunk_text[:200]

    q_tokens = set(re.findall(r'\w+', strip_accents(query)))
    best_sent = sentences[0]
    best_score = -1

    for s in sentences:
        s_tokens = set(re.findall(r'\w+', strip_accents(s)))
        overlap = len(q_tokens.intersection(s_tokens))
        if overlap > best_score:
            best_score = overlap
            best_sent = s

    # Certifica garantia absoluta de substring
    if best_sent in chunk_text:
        return best_sent
    return chunk_text[:200]


class HybridRetriever:
    """Pipeline principal de Recuperação Híbrida (Vetores + Grafo) do Assistente_BDGraph."""

    def __init__(self, root: Path = ROOT, model_name: str = DEFAULT_MODEL):
        self.root = root
        self.chunks, self.texts, self.sources = load_corpus(root)
        self.concepts, self.relations, self.chunk_mentions = load_graph_data(root, include_sample=True)
        self.model_name = model_name
        self.embedder = DenseEmbedder(model_name)
        self._precomputed_embeddings: Optional[Dict[str, List[float]]] = None

    @property
    def precomputed_embeddings(self) -> Dict[str, List[float]]:
        if self._precomputed_embeddings is None:
            if EMBEDDINGS_FILE.exists():
                data = load_json(EMBEDDINGS_FILE)
                self._precomputed_embeddings = data.get('embeddings', {})
            else:
                self._precomputed_embeddings = self.generate_all_embeddings()
        return self._precomputed_embeddings

    def generate_all_embeddings(self, save: bool = True) -> Dict[str, List[float]]:
        """Gera embeddings vetoriais para todos os 59 chunks do corpus."""
        chunk_ids = list(self.chunks.keys())
        chunk_texts = [self.texts[cid] for cid in chunk_ids]
        raw_vecs = self.embedder.encode(chunk_texts)
        embeddings = {cid: vec.tolist() for cid, vec in zip(chunk_ids, raw_vecs)}

        if save:
            EMBEDDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                'model': self.model_name,
                'dimensions': VECTOR_DIMENSION,
                'count': len(embeddings),
                'embeddings': embeddings
            }
            with open(EMBEDDINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)

        self._precomputed_embeddings = embeddings
        return embeddings

    def retrieve(self, question: str, top_k: int = 5, max_hops: int = 4, session: Any = None) -> Dict[str, Any]:
        """Executa a recuperação híbrida completa e monta o pacote de evidências."""
        # 1. Busca Vetorial
        query_vec = self.embedder.encode(question)[0]
        if session:
            # Executa no Neo4j com índice vetorial
            cypher_vec = (
                "CALL db.index.vector.queryNodes('chunk_embedding', $k, $q) YIELD node, score "
                "RETURN node.chunk_id AS chunk_id, score"
            )
            res = session.run(cypher_vec, k=top_k * 2, q=query_vec.tolist())
            vector_ranks = [(r['chunk_id'], float(r['score'])) for r in res]
        else:
            vector_ranks = vector_search(query_vec, self.precomputed_embeddings, top_k=top_k * 2)

        # 2. Identificação de Conceitos
        matched_concepts = identify_concepts(question, self.concepts)

        # 3. Travessia Multi-hop e Algoritmo de Grafo
        traversed_edges, touched_ids = traverse_graph(matched_concepts, self.relations, max_hops=max_hops)

        # Lista chunks de evidência originados do grafo
        graph_chunk_ids = []
        rel_by_chunk = {}
        for edge in traversed_edges:
            for cid in edge.get('evidence_chunk_ids', []):
                if cid in self.chunks and cid not in graph_chunk_ids:
                    graph_chunk_ids.append(cid)
                    rel_by_chunk[cid] = edge

        # Adiciona chunks que mencionam diretamente os conceitos identificados
        for c in matched_concepts:
            cid_concept = c['concept_id']
            for cid_chunk, c_set in self.chunk_mentions.items():
                if cid_concept in c_set and cid_chunk not in graph_chunk_ids:
                    graph_chunk_ids.append(cid_chunk)

        # 4. Fusão Híbrida (RRF)
        fused_chunks = reciprocal_rank_fusion(vector_ranks, graph_chunk_ids, k_rrf=60)
        selected_chunk_ids = [cid for cid, _ in fused_chunks[:top_k]]

        # 5. Monta a lista de evidências
        evidence_list = []
        used_chunks = set()

        # Prioriza evidências vindas das relações do grafo
        for edge in traversed_edges:
            for cid in edge.get('evidence_chunk_ids', []):
                if cid in selected_chunk_ids and cid not in used_chunks:
                    used_chunks.add(cid)
                    c_record = self.chunks[cid]
                    doc_id = c_record['document_id']
                    source_meta = self.sources.get(doc_id, {})
                    quote = edge.get('evidence_quote')
                    if not quote or quote not in self.texts[cid]:
                        quote = find_best_quote(self.texts[cid], question)

                    rel_info = {
                        'relation_id': edge.get('relation_id', 'R_inferred'),
                        'type': edge['type'],
                        'source': edge['source'],
                        'target': edge['target']
                    }
                    section_p = format_section_path(c_record, source_meta.get('title', doc_id))
                    evidence_list.append({
                        'chunk_id': cid,
                        'document_id': doc_id,
                        'title': source_meta.get('title', doc_id),
                        'source_url': c_record.get('source_url') or source_meta.get('source_url', ''),
                        'section_path': section_p,
                        'quote': quote,
                        'review_status': edge.get('review_status', 'accepted'),
                        'origin': 'graph',
                        'relation': rel_info
                    })

        # Adiciona as evidências restantes selecionadas por busca vetorial / menção
        for cid in selected_chunk_ids:
            if cid not in used_chunks:
                used_chunks.add(cid)
                c_record = self.chunks[cid]
                doc_id = c_record['document_id']
                source_meta = self.sources.get(doc_id, {})
                quote = find_best_quote(self.texts[cid], question)
                origin = 'concept' if cid in self.chunk_mentions else 'vector'
                section_p = format_section_path(c_record, source_meta.get('title', doc_id))

                evidence_list.append({
                    'chunk_id': cid,
                    'document_id': doc_id,
                    'title': source_meta.get('title', doc_id),
                    'source_url': c_record.get('source_url') or source_meta.get('source_url', ''),
                    'section_path': section_p,
                    'quote': quote,
                    'review_status': 'accepted',
                    'origin': origin,
                    'relation': None
                })

        # Conceitos enriquecidos para o contrato
        final_concepts = [
            {
                'concept_id': c['concept_id'],
                'canonical_name': c['canonical_name'],
                'name_pt': c['name_pt']
            }
            for c in matched_concepts
        ]

        bundle = {
            'question': question,
            'language': 'pt-BR',
            'retrieval': {
                'strategy': 'hybrid',
                'channels': ['graph', 'vector'] if graph_chunk_ids else ['vector'],
                'graph_executed': True,
                'max_hops': max_hops,
                'graph_algorithm': 'shortest_path + degree_centrality',
                'model': self.model_name,
                'dimension': VECTOR_DIMENSION
            },
            'concepts': final_concepts,
            'evidence': evidence_list,
            '_provenance': 'Recuperação Híbrida GraphRAG / KAG - Assistente_BDGraph (Parte 3)'
        }
        return bundle


def validate_retrieval_bundle(bundle: Dict[str, Any], corpus_texts: Dict[str, str]) -> List[str]:
    """Valida o pacote de evidências estritamente contra as regras do contrato da Parte 4."""
    errors = []
    if not isinstance(bundle, dict):
        return ['Bundle must be a dict']
    if not bundle.get('question'):
        errors.append('Question is empty')
    evidence = bundle.get('evidence', [])
    if not evidence:
        errors.append('Evidence list is empty')

    retrieval = bundle.get('retrieval', {})
    channels = retrieval.get('channels', [])
    if any(c not in {'vector', 'graph'} for c in channels):
        errors.append(f'Invalid channel in {channels}')

    for idx, ev in enumerate(evidence, 1):
        cid = ev.get('chunk_id')
        if not cid or not CHUNK_ID_RE.fullmatch(cid):
            errors.append(f'Evidence {idx}: invalid chunk_id {cid}')
        elif cid not in corpus_texts:
            errors.append(f'Evidence {idx}: chunk_id {cid} not in corpus')

        quote = ev.get('quote')
        if not quote or not isinstance(quote, str) or not quote.strip():
            errors.append(f'Evidence {idx}: quote is empty')
        elif cid in corpus_texts and quote not in corpus_texts[cid]:
            errors.append(f'Evidence {idx}: quote is not a verbatim substring of chunk {cid}')

        if ev.get('origin') not in {'vector', 'graph', 'concept'}:
            errors.append(f'Evidence {idx}: invalid origin {ev.get("origin")}')

        if ev.get('review_status') not in {'accepted', 'pending', 'flagged'}:
            errors.append(f'Evidence {idx}: invalid review_status {ev.get("review_status")}')

    return errors


def sync_embeddings_to_neo4j(embeddings_file: Path = EMBEDDINGS_FILE, uri: str = None, user: str = None, password: str = None):
    """Carrega os embeddings para os nós :Chunk no banco Neo4j."""
    import neo4j
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')

    uri = uri or os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    user = user or os.environ.get('NEO4J_USER', 'neo4j')
    password = password or os.environ.get('NEO4J_PASSWORD', 'password')
    database = os.environ.get('NEO4J_DATABASE', 'neo4j')

    data = load_json(embeddings_file)
    embeddings = data['embeddings']
    rows = [{'chunk_id': cid, 'embedding': emb} for cid, emb in embeddings.items()]

    driver = neo4j.GraphDatabase.driver(uri, auth=(user, password))
    with driver.session(database=database) as session:
        # 1. Aplica índice vetorial se não existir
        cypher_idx = (
            f"CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS "
            f"FOR (c:Chunk) ON (c.embedding) "
            f"OPTIONS {{indexConfig: {{`vector.dimensions`: {data['dimensions']}, `vector.similarity_function`: 'cosine'}}}}"
        )
        session.run(cypher_idx).consume()

        # 2. Grava embeddings
        cypher_set = (
            "UNWIND $rows AS row MATCH (c:Chunk {chunk_id: row.chunk_id}) "
            "SET c.embedding = row.embedding "
            "RETURN count(c) AS count"
        )
        res = session.run(cypher_set, rows=rows).single()
        print(f"Sucesso: {res['count']} nós Chunk atualizados com embeddings no Neo4j.")
    driver.close()


def main():
    parser = argparse.ArgumentParser(description='Mecanismo de Recuperação Híbrida - GraphRAG/KAG')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Subcomando embed
    p_embed = subparsers.add_parser('embed', help='Gera embeddings para o corpus')
    p_embed.add_argument('--model', default=DEFAULT_MODEL, help='Modelo HuggingFace')

    # Subcomando ingest-embeddings
    p_ingest = subparsers.add_parser('ingest-embeddings', help='Carrega embeddings no Neo4j')

    # Subcomando search
    p_search = subparsers.add_parser('search', help='Executa busca híbrida')
    p_search.add_argument('--query', required=True, help='Pergunta do usuário em linguagem natural')
    p_search.add_argument('--top-k', type=int, default=5, help='Quantidade de trechos a recuperar')
    p_search.add_argument('--max-hops', type=int, default=4, help='Máximo de saltos na travessia de grafo')
    p_search.add_argument('--output', help='Caminho para salvar o bundle JSON de evidências')
    p_search.add_argument('--neo4j', action='store_true',
                          help='Usa o índice vetorial nativo do Neo4j (aproximado) em vez dos vetores em memória')

    args = parser.parse_args()

    if args.command == 'embed':
        retriever = HybridRetriever(ROOT, model_name=args.model)
        embs = retriever.generate_all_embeddings(save=True)
        print(f"Gerados embeddings para {len(embs)} trechos em {EMBEDDINGS_FILE}.")

    elif args.command == 'ingest-embeddings':
        sync_embeddings_to_neo4j()

    elif args.command == 'search':
        retriever = HybridRetriever(ROOT)
        session = None
        driver = None
        if args.neo4j:
            # Consulta o índice vetorial nativo (`chunk_embedding`) em vez dos vetores versionados.
            # A busca no Neo4j é aproximada (HNSW); a versão em memória é exata. O padrão é a exata.
            import neo4j
            from dotenv import load_dotenv
            load_dotenv(ROOT / '.env')
            driver = neo4j.GraphDatabase.driver(
                os.environ.get('NEO4J_URI', 'bolt://localhost:7687'),
                auth=(os.environ.get('NEO4J_USER', 'neo4j'),
                      os.environ.get('NEO4J_PASSWORD', 'password')))
            session = driver.session(database=os.environ.get('NEO4J_DATABASE', 'neo4j'))
        try:
            bundle = retriever.retrieve(args.query, top_k=args.top_k,
                                        max_hops=args.max_hops, session=session)
        finally:
            if session is not None:
                session.close()
            if driver is not None:
                driver.close()
        errs = validate_retrieval_bundle(bundle, retriever.texts)
        if errs:
            print(f"Atenção na validação do bundle: {errs}")
        output_json = json.dumps(bundle, indent=2, ensure_ascii=False)
        if args.output:
            out_file = Path(args.output)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(output_json, encoding='utf-8')
            print(f"Bundle salvo em: {out_file}")
        else:
            print(output_json)


if __name__ == '__main__':
    main()
