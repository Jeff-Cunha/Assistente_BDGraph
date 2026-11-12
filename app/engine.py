"""In-process engine for the interface: modules, database access and the answer pipeline.

The interface does not reimplement any part of the pipeline. It loads the scripts from
partes 2-4 exactly as they are, so a change in the guard, in the executor or in the
grounding check reaches the screen without a copy.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import time
import unicodedata
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / 'work' / 'interface-runs'
OLLAMA_BASE = 'http://127.0.0.1:11434'
MAX_EVIDENCE_HOPS = 3


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


executor = _load('neo4j_executor', 'neo4j-executor.py')
guard = _load('guard_cypher', 'guard-cypher.py')
grounding = _load('answer_grounding', 'answer-grounding.py')
run_answer = _load('run_answer_ollama', 'run-answer-ollama.py')

_CORPUS = None


def corpus_texts():
    """Literal quote checking against the corpus, loaded once."""
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = grounding.load_corpus_texts(ROOT)
    return _CORPUS


class EngineError(RuntimeError):
    """A failure the interface reports as a message, never as a partial answer."""


@contextmanager
def database():
    """One read-only session against the graph of parte 2."""
    try:
        config = executor.load_config(ROOT)
        driver = executor.connect(config)
    except executor.ExecutorError as exc:      # Neo4j down or misconfigured
        raise EngineError(str(exc)) from None
    try:
        yield driver, config['NEO4J_DATABASE']
    finally:
        driver.close()


def read(driver, database_name, query, parameters, timeout=10.0):
    return executor.read_rows(driver, query, parameters, database_name, timeout)


def concepts(driver, database_name):
    """Concepts with their two names, used to find what a free question is about."""
    rows = read(driver, database_name,
                'MATCH (c:Concept) RETURN c.concept_id AS id, c.canonical_name AS en, '
                'c.name_pt AS pt ORDER BY c.concept_id', {})
    return [{'id': row['id'], 'canonical_name': row['en'], 'name_pt': row['pt']}
            for row in rows if row.get('id')]


_FULLTEXT_UNSAFE = re.compile(r'[^\w\s]+', re.UNICODE)


def fulltext_query(text):
    """Lucene syntax free text: words only, so a user's punctuation cannot break the query."""
    words = [w for w in _FULLTEXT_UNSAFE.sub(' ', text or '').split() if len(w) > 1]
    return ' OR '.join(words[:8])


def search_concepts(driver, database_name, text, limit=6):
    """Concepts found by the fulltext index over names, aliases and the Portuguese name.

    This is the index declared in db/schema.cypher as `concept_names`: it ignores accents and
    ranks the names the question shares with the graph. It is used when the lexical ranking of
    the planner finds nothing, so the screen can still offer a term that exists.
    """
    query = fulltext_query(text)
    if not query:
        return []
    rows = read(driver, database_name,
                "CALL db.index.fulltext.queryNodes('concept_names', $q) "
                "YIELD node, score RETURN node.concept_id AS id, node.name_pt AS pt, "
                "node.canonical_name AS en, score ORDER BY score DESC LIMIT $limit",
                {'q': query, 'limit': int(limit)})
    return [{'id': row['id'], 'name_pt': row.get('pt') or row.get('en'),
             'score': round(float(row.get('score') or 0), 3)} for row in rows if row.get('id')]


def graph_stats(driver, database_name):
    rows = read(driver, database_name,
                'MATCH (n) RETURN head(labels(n)) AS label, count(*) AS total', {})
    stats = {row['label']: row['total'] for row in rows}
    edges = read(driver, database_name,
                 'MATCH ()-[r]->() WHERE type(r) IN $types RETURN count(r) AS total',
                 {'types': sorted(guard.SEMANTIC_RELATION_TYPES)})[0]['total']
    return {'nodes': stats, 'semantic_relations': edges}


def ollama_status():
    """Model list and server version; a stopped server is reported, never retried silently."""
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with client.open(OLLAMA_BASE + '/api/version', timeout=5) as response:
            version = json.load(response).get('version')
        with client.open(OLLAMA_BASE + '/api/tags', timeout=5) as response:
            models = [{'name': row.get('name'), 'size': row.get('size'),
                       'digest': row.get('digest')}
                      for row in json.load(response).get('models', [])
                      if row.get('name') and not row.get('remote_host')]
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {'online': False, 'error': type(exc).__name__, 'models': []}
    return {'online': True, 'version': version, 'models': models}


def health():
    """Everything the screen shows before the first question."""
    report = {'neo4j': {'online': False}, 'ollama': ollama_status()}
    try:
        with database() as (driver, database_name):
            report['neo4j'] = {'online': True, 'database': database_name,
                               **graph_stats(driver, database_name)}
    except EngineError as exc:
        report['neo4j'] = {'online': False, 'error': str(exc)}
    return report


def text_evidence(driver, database_name, concept, limit=6):
    """Literal quotes from the chunks that mention a concept, for concepts with no edge.

    The sentence is cut from the stored chunk text, never rewritten, so the grounding check
    can still verify it character by character.
    """
    rows = read(driver, database_name,
                'MATCH (c:Concept {concept_id: $id})<-[:MENTIONS]-(ch:Chunk) '
                'RETURN ch.chunk_id AS chunk_id LIMIT $limit',
                {'id': concept['id'], 'limit': limit})
    chunk_ids = [row['chunk_id'] for row in rows if row.get('chunk_id')]
    if not chunk_ids:
        return []
    metadata = executor.chunk_metadata(driver, chunk_ids, database_name)
    texts = corpus_texts()
    terms = [concept.get('name_pt') or '', concept.get('canonical_name') or '']
    evidence = []
    for chunk_id in chunk_ids:
        text = texts.get(chunk_id)
        if not text:
            continue
        quote = extract_quote(text, terms)
        if not quote:
            continue
        meta = metadata.get(chunk_id) or {}
        evidence.append({'chunk_id': chunk_id, 'document_id': meta.get('document_id'),
                         'title': meta.get('title'), 'source_url': meta.get('source_url'),
                         'section_path': meta.get('section_path'), 'quote': quote,
                         'review_status': 'pending', 'origin': 'graph',
                         'relation': None})
    return evidence


SENTENCE_BREAK = re.compile(r'(?<=[.!?])\s+')
MAX_QUOTE = 420


def _plain(text):
    lowered = unicodedata.normalize('NFD', text or '').lower()
    return ''.join(char for char in lowered if unicodedata.category(char) != 'Mn')


def extract_quote(text, terms):
    """First sentence of the chunk that names the concept, trimmed to a readable quote."""
    for sentence in SENTENCE_BREAK.split(text):
        if len(sentence.strip()) < 20:
            continue
        plain = _plain(sentence)
        if any(term and _plain(term) in plain for term in terms):
            return sentence.strip()[:MAX_QUOTE]
    return ''


def _ollama_chat(payload, timeout):
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(
        OLLAMA_BASE + '/api/chat', method='POST',
        headers={'Content-Type': 'application/json'},
        data=json.dumps(payload).encode('utf-8'))
    try:
        with client.open(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise EngineError(f'O modelo recusou a chamada (HTTP {exc.code}).') from None
    except (urllib.error.URLError, OSError) as exc:
        raise EngineError('O Ollama não respondeu; verifique se está rodando.') from None


MODE_HYBRID = 'hybrid'
MODE_GRAPH = 'graph'
MODES = (MODE_HYBRID, MODE_GRAPH)

_RETRIEVER = None


def retriever():
    """The hybrid retriever of parte 3, built once: it loads a sentence encoder."""
    global _RETRIEVER
    if _RETRIEVER is None:
        try:
            module = _load('retrieval_parte3', 'retrieval.py')
            _RETRIEVER = module.HybridRetriever()
        except Exception as exc:                 # missing dependency or corpus, not a typo
            raise EngineError(
                'A recupera\u00e7\u00e3o h\u00edbrida n\u00e3o p\u00f4de ser carregada: '
                f'{type(exc).__name__}: {exc}. Instale requirements-retrieval.txt ou use o '
                'modo grafo.') from None
    return _RETRIEVER


def hybrid_bundle(question, top_k=5, max_hops=MAX_EVIDENCE_HOPS):
    """Evidence from vector search plus graph traversal, exactly as parte 3 builds it."""
    try:
        return retriever().retrieve(question, top_k=top_k, max_hops=max_hops)
    except EngineError:
        raise
    except Exception as exc:
        raise EngineError(f'A recupera\u00e7\u00e3o h\u00edbrida falhou: '
                          f'{type(exc).__name__}: {exc}') from None


def bundle_graph(bundle, catalog=None):
    """Draw the relations the bundle actually used; a hybrid bundle carries no path query."""
    names = {}
    for identifier, concept in (catalog or {}).items():    # every concept of the graph
        if isinstance(concept, dict):
            names[identifier] = (concept.get('name_pt') or concept.get('canonical_name')
                                 or identifier)
    for concept in bundle.get('concepts') or []:           # the ones matched by the question
        names[concept.get('concept_id')] = (concept.get('name_pt')
                                            or concept.get('canonical_name')
                                            or concept.get('concept_id'))
    paths, drawn = [], set()
    for item in bundle.get('evidence') or []:
        relation = item.get('relation') or {}
        source, target, kind = relation.get('source'), relation.get('target'), relation.get('type')
        if not (source and target and kind) or (source, target, kind) in drawn:
            continue
        drawn.add((source, target, kind))
        paths.append({
            'nodes': [{'label': 'Concept', 'id': side, 'name': names.get(side, side),
                       'name_pt': names.get(side, side)} for side in (source, target)],
            'relationships': [{
                'type': kind, 'relation_id': relation.get('relation_id'),
                'source': source, 'target': target,
                'review_status': item.get('review_status'),
                'evidence_quotes_json': json.dumps(
                    [{'chunk_id': item.get('chunk_id'), 'quote': item.get('quote')}],
                    ensure_ascii=False)}],
        })
    retrieval = bundle.get('retrieval') or {}
    return {'mode': MODE_HYBRID, 'cypher': None, 'parameters': None, 'paths': paths,
            'channels': retrieval.get('channels'),
            'graph_algorithm': retrieval.get('graph_algorithm'),
            'origins': sorted({item.get('origin') for item in bundle.get('evidence') or []
                               if item.get('origin')})}


def _hybrid_context(question, top_k, max_hops, seen):
    seen('Recuperando por vetor e por grafo')
    bundle = hybrid_bundle(question, top_k, max_hops)
    catalog = getattr(retriever(), 'concepts', None) or {}
    reading = {'strategy': 'hybrid',
               'explanation': ('Recupera\u00e7\u00e3o h\u00edbrida: busca vetorial somada \u00e0 '
                               'travessia do grafo por fus\u00e3o de ranks, com o caminho mais '
                               'curto entre os conceitos identificados.')}
    return bundle, bundle_graph(bundle, catalog), reading, None


def _graph_context(question, max_hops, db_timeout, seen):
    from . import planner                            # local: avoids a cycle at import time
    with database() as (driver, database_name):
        seen('Interpretando a pergunta')
        plan, reading = planner.build_plan(driver, database_name, question, max_hops)
        seen(f'Consultando o grafo ({len(plan["hops"])} salto(s))')
        executed = executor.execute_plan(driver, plan, database_name, db_timeout, max_hops)
        metadata = executor.chunk_metadata(
            driver, executor.evidence_chunk_ids(executed['rows']), database_name, db_timeout)
        graph = {'mode': MODE_GRAPH, 'cypher': executed['cypher'],
                 'parameters': executed['parameters'], 'paths': executed['rows']}
        bundle = executor.bundle_from_paths(question, executed['rows'], metadata)
        if bundle.get('evidence'):
            return bundle, graph, reading, plan
        seen('Buscando os trechos que mencionam o conceito')
        plan = planner.text_plan(reading['matched'][0]['id'], max_hops)
        executed = executor.execute_plan(driver, plan, database_name, db_timeout, max_hops)
        graph = {'mode': MODE_GRAPH, 'cypher': executed['cypher'],
                 'parameters': executed['parameters'], 'paths': executed['rows']}
        concept = {'id': reading['matched'][0]['id'],
                   'name_pt': reading['matched'][0]['name_pt'],
                   'canonical_name': reading['matched'][0]['canonical_name']}
        group = dict(reading['matched'][0])
        evidence = text_evidence(driver, database_name, concept)
        reading['strategy'] = 'text'
        reading['explanation'] = (
            f'A pergunta foi ligada a "{concept["name_pt"]}", que ainda n\u00e3o tem rela\u00e7\u00e3o '
            'sem\u00e2ntica no grafo; a resposta vem dos trechos que mencionam o conceito.')
        reading['matched'] = [group] + reading['matched'][1:]
        bundle = {'question': question, 'language': 'pt-BR',
                  'retrieval': {'strategy': 'graph-text', 'channels': ['graph'],
                                'graph_executed': True, 'max_hops': 0},
                  'concepts': [{'concept_id': concept['id'],
                                'canonical_name': concept['canonical_name'],
                                'name_pt': concept['name_pt']}],
                  'evidence': evidence}
        return bundle, graph, reading, plan


def answer_from_evidence(question, bundle, model='qwen3:8b', graph=None, reading=None,
                         plan=None, mode=None, timeout=900, output_tokens=2048, context=16384,
                         on_step=None):
    """Ask the model about an already retrieved bundle and verify the answer.

    Kept separate from retrieval so an evaluation can feed the same bundle builder the
    interface uses, and so a comparison can vary only the retrieval step."""
    started = time.monotonic()
    seen = on_step or (lambda label: None)
    model_info = {'provider': 'ollama_local', 'model': model, 'model_digest': None,
                  'settings': {'num_ctx': context, 'num_predict': output_tokens,
                               'temperature': 0, 'seed': 42, 'think': False}}
    if not bundle.get('evidence'):
        answer = grounding.abstention_response(
            question, 'A recupera\u00e7\u00e3o n\u00e3o encontrou evid\u00eancia literal para esta '
                      'pergunta; o modelo n\u00e3o foi chamado.', graph=graph, model=model_info)
    else:
        seen('Chamando o modelo local')
        bundle = grounding.normalize_bundle(bundle)
        prompt = run_answer.build_prompt(bundle)
        payload = run_answer.build_payload(prompt, model, context, output_tokens)
        provider_response = _ollama_chat(payload, timeout)
        seen('Verificando cita\u00e7\u00f5es')
        raw = run_answer.parse_response(provider_response)
        answer = grounding.evaluate(bundle, raw, corpus_texts(), graph, model_info)
        answer['run'] = {'duration_seconds': round(time.monotonic() - started, 1),
                         'output_tokens': provider_response.get('eval_count'),
                         'prompt_tokens': provider_response.get('prompt_eval_count'),
                         'bundle_sha256': hashlib.sha256(
                             json.dumps(bundle, ensure_ascii=False,
                                        sort_keys=True).encode('utf-8')).hexdigest()}
    if plan is not None:
        answer['plan'] = plan
    answer['mode'] = mode
    answer['reading'] = reading or {'strategy': mode or 'desconhecida'}
    answer['elapsed_seconds'] = round(time.monotonic() - started, 1)
    answer['answered_at'] = datetime.now(timezone.utc).isoformat()
    return answer


def answer_question(question, model='qwen3:8b', mode=MODE_HYBRID, max_hops=MAX_EVIDENCE_HOPS,
                    top_k=5, timeout=900, db_timeout=10.0, output_tokens=2048, context=16384,
                    on_step=None):
    """Retrieve, ask the model and verify. Returns the contract answer.

    `mode` chooses the retrieval: hybrid (parte 3, vector plus graph) or graph (a validated
    query plan). `on_step` receives short labels so the screen can show where the run is."""
    seen = on_step or (lambda label: None)
    if mode == MODE_GRAPH:
        bundle, graph, reading, plan = _graph_context(question, max_hops, db_timeout, seen)
    elif mode == MODE_HYBRID:
        bundle, graph, reading, plan = _hybrid_context(question, top_k, max_hops, seen)
    else:
        raise EngineError(f'Modo de recupera\u00e7\u00e3o desconhecido: {mode}')
    return answer_from_evidence(question, bundle, model=model, graph=graph, reading=reading,
                                plan=plan, mode=mode, timeout=timeout,
                                output_tokens=output_tokens, context=context, on_step=seen)


def save_run(job_id, answer):
    """Keep every run on disk; the screen is a view, the file is the record."""
    target = RUNS / job_id
    target.mkdir(parents=True, exist_ok=True)
    path = target / 'answer.json'
    path.write_text(json.dumps(answer, ensure_ascii=False, indent=2), encoding='utf-8')
    return path
