"""Ingestão idempotente do corpus e da extração revisada no Neo4j (parte 2).

Uso (na raiz do repositório):
    python scripts/neo4j_ingest.py schema                    # restrições e índices
    python scripts/neo4j_ingest.py ingest --dry-run          # valida tudo, sem tocar no banco
    python scripts/neo4j_ingest.py ingest                    # grava e verifica
    python scripts/neo4j_ingest.py verify                    # só confere o banco

Regras seguidas (ver docs/entrega-parte1-atualizada.md e docs/modelo-grafo.md):
- identidade por ID estável (document_id, chunk_id, concept_id), nunca por nome;
- MERGE + restrição de unicidade: rodar de novo não duplica nada;
- conceitos repetidos entre arquivos são unidos (aliases e evidências), não sobrescritos;
- referência inválida (chunk, conceito, citação, tipo de relação) = erro explícito;
- a carga é uma única transação: ou entra tudo, ou nada;
- nada é apagado do banco, e propriedades de outras partes (ex.: embedding) são preservadas.
"""
import argparse
import hashlib
import json
import os
import sys
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ROOT / 'db' / 'schema.cypher'
RELEASE_FILE = 'data/release/current.json'
SAMPLE_FILE = 'data/extraction/sample.json'
BATCH_SIZE = 500

# Tipo de relação não pode ser parâmetro no Cypher: só entra no texto da consulta
# se estiver nesta lista (contrato 0.1.2 da parte 1).
ALLOWED_RELATION_TYPES = (
    'IS_A', 'SUPPORTS', 'REQUIRES', 'GOVERNS', 'TYPICALLY_USED_IN', 'COMBINES',
    'HAS_FORM', 'PRESERVES', 'RETRIEVES', 'FILTERS', 'GROUPS', 'AGGREGATES',
    'EVALUATED_BEFORE', 'REMOVES_DUPLICATES',
)
REVIEW_RANK = {'flagged': 0, 'pending': 1, 'accepted': 2}  # vale o "mais fraco"
REQUIRED_CONSTRAINTS = ('document_id_unique', 'chunk_id_unique', 'concept_id_unique')
REQUIRED_INDEXES = (
    'chunk_document_id', 'chunk_content_type', 'concept_category',
    'concept_canonical_name', 'concept_names', 'chunk_text',
)


class IngestError(Exception):
    """Dados ou configuração inválidos; a mensagem lista todos os problemas."""


# ---------------------------------------------------------------- utilidades

def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def unique(items):
    return list(OrderedDict.fromkeys(items))


def is_scalar(value):
    return isinstance(value, (str, int, float, bool))


def neo_props(record, rename=None, skip=()):
    """Converte um registro em propriedades aceitas pelo Neo4j.

    Neo4j só guarda valores simples ou listas de valores simples do mesmo tipo.
    Qualquer outra coisa (objetos, listas de listas) vira texto JSON em <campo>_json.
    Valores nulos são omitidos.
    """
    rename = rename or {}
    props = {}
    for key, value in record.items():
        if key in skip or value is None:
            continue
        name = rename.get(key, key)
        if is_scalar(value):
            props[name] = value
        elif isinstance(value, list) and all(is_scalar(v) for v in value) and len({type(v) for v in value}) <= 1:
            props[name] = value
        else:
            props[name + '_json'] = dumps(value)
    return props


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------- leitura da base

def load_extractions(root, include_sample=False, check_hashes=True):
    """Lê SOMENTE os primary_files do índice atual (e, opcionalmente, o sample).

    A ordem importa: o primeiro arquivo que traz um conceito define os campos de
    texto (nome em português, descrição); os demais só acrescentam aliases e evidências.
    O sample fica por último para nunca substituir um resumo revisado por um antigo.
    """
    release = read_json(root / RELEASE_FILE)
    paths = []
    problems = []
    for entry in release['primary_files']:
        paths.append(entry['path'])
        if check_hashes and sha256_file(root / entry['path']) != entry['sha256']:
            problems.append(f"Hash diferente do índice da release: {entry['path']} "
                            f"(use --no-hash-check só se tiver certeza do motivo, ex.: quebra de linha no Windows).")
    if include_sample:
        paths.append(SAMPLE_FILE)
    if problems:
        raise IngestError('\n'.join(problems))
    return [{'path': p, 'data': read_json(root / p)} for p in paths], release


def document_row(doc):
    row = neo_props(doc, rename={
        'final_url': 'source_url',
        'version_or_edition': 'version',
        'authors_or_responsible_institution': 'authors',
    })
    lic = doc.get('license') or {}
    if lic.get('name'):
        row['license_name'] = lic['name']
    if lic.get('license_url'):
        row['license_url'] = lic['license_url']
    return row


def merge_concepts(extractions, problems):
    merged = OrderedDict()
    for ext in extractions:
        method = ext['data']['extraction_method']
        for c in ext['data']['concepts']:
            cid = c['concept_id']
            provenance = {
                'method': method, 'file': ext['path'], 'name_pt': c['name_pt'],
                'description_pt': c['description_pt'], 'review_status': c['review_status'],
                'review_note': c.get('review_note'),
            }
            if cid not in merged:
                merged[cid] = {
                    'concept_id': cid, 'canonical_name': c['canonical_name'], 'name_pt': c['name_pt'],
                    'aliases': list(c['aliases']), 'category': c['category'],
                    'description_pt': c['description_pt'], 'review_status': c['review_status'],
                    'review_note': c.get('review_note'), 'methods': [method],
                    'evidence': list(c['evidence']), 'provenance': [provenance],
                }
                continue
            m = merged[cid]
            for field in ('canonical_name', 'category'):
                if m[field] != c[field]:
                    problems.append(f"Conceito {cid}: '{field}' diverge entre arquivos "
                                    f"({m[field]!r} x {c[field]!r}); resolver na parte 1.")
            m['aliases'] = unique(m['aliases'] + list(c['aliases']))
            m['methods'] = unique(m['methods'] + [method])
            m['evidence'] = unique_evidence(m['evidence'] + list(c['evidence']))
            if REVIEW_RANK[c['review_status']] < REVIEW_RANK[m['review_status']]:
                m['review_status'] = c['review_status']
            m['provenance'].append(provenance)
    return merged


def unique_evidence(evidence):
    seen, result = set(), []
    for e in evidence:
        key = (e['chunk_id'], e['quote'])
        if key not in seen:
            seen.add(key)
            result.append(e)
    return result


def concept_row(m):
    row = {
        'concept_id': m['concept_id'], 'canonical_name': m['canonical_name'], 'name_pt': m['name_pt'],
        'aliases': m['aliases'], 'category': m['category'], 'description_pt': m['description_pt'],
        'review_status': m['review_status'], 'extraction_methods': m['methods'],
        'evidence_chunk_ids': unique(e['chunk_id'] for e in m['evidence']),
        'evidence_quotes_json': dumps(m['evidence']),
        'provenance_json': dumps(m['provenance']),
    }
    if m['review_note']:
        row['review_note'] = m['review_note']
    return row


def merge_relations(extractions):
    merged = OrderedDict()
    for ext in extractions:
        method = ext['data']['extraction_method']
        for r in ext['data']['relations']:
            key = (r['source'], r['type'], r['target'])
            provenance = {
                'method': method, 'file': ext['path'], 'relation_id': r['relation_id'],
                'assertion_kind': r['assertion_kind'], 'review_status': r['review_status'],
                'review_note': r.get('review_note'),
            }
            if key not in merged:
                merged[key] = {
                    'source': r['source'], 'type': r['type'], 'target': r['target'],
                    'relation_ids': [r['relation_id']], 'assertion_kind': r['assertion_kind'],
                    'review_status': r['review_status'], 'review_note': r.get('review_note'),
                    'methods': [method], 'evidence': list(r['evidence']), 'provenance': [provenance],
                }
                continue
            m = merged[key]
            m['relation_ids'] = unique(m['relation_ids'] + [r['relation_id']])
            m['methods'] = unique(m['methods'] + [method])
            m['evidence'] = unique_evidence(m['evidence'] + list(r['evidence']))
            if r['assertion_kind'] == 'inferred':
                m['assertion_kind'] = 'inferred'
            if REVIEW_RANK[r['review_status']] < REVIEW_RANK[m['review_status']]:
                m['review_status'] = r['review_status']
            m['provenance'].append(provenance)
    return merged


def relation_props(m):
    props = {
        'relation_id': m['relation_ids'][0], 'relation_ids': m['relation_ids'],
        'assertion_kind': m['assertion_kind'], 'review_status': m['review_status'],
        'extraction_methods': m['methods'],
        'evidence_chunk_ids': unique(e['chunk_id'] for e in m['evidence']),
        'evidence_quotes_json': dumps(m['evidence']),
        'provenance_json': dumps(m['provenance']),
    }
    if m['review_note']:
        props['review_note'] = m['review_note']
    return props


def check_evidence(owner, evidence, texts, problems):
    for e in evidence:
        text = texts.get(e['chunk_id'])
        if text is None:
            problems.append(f"{owner}: evidência aponta para chunk inexistente {e['chunk_id']}.")
        elif e['quote'] not in text:
            problems.append(f"{owner}: citação não está literalmente em {e['chunk_id']}: {e['quote'][:60]!r}...")


def build_payload(root=ROOT, include_sample=False, check_hashes=True):
    """Lê tudo, une, valida e devolve o que será gravado. Não acessa o banco."""
    root = Path(root)
    problems = []
    extractions, release = load_extractions(root, include_sample, check_hashes)

    documents = OrderedDict()
    for d in read_json(root / 'corpus/metadata/sources.json'):
        if d['document_id'] in documents:
            problems.append(f"document_id repetido: {d['document_id']}.")
        documents[d['document_id']] = document_row(d)

    pages = read_jsonl(root / 'corpus/chunks/chunks.jsonl')
    figures = read_jsonl(root / 'corpus/chunks/figure_supplements.jsonl')
    page_ids = {c['chunk_id'] for c in pages}
    chunks, texts, contains, supplements = OrderedDict(), {}, [], []
    for record, is_figure in [(r, False) for r in pages] + [(r, True) for r in figures]:
        cid = record['chunk_id']
        if cid in chunks:
            problems.append(f'chunk_id repetido: {cid}.')
            continue
        if record['document_id'] not in documents:
            problems.append(f"Chunk {cid} aponta para documento inexistente {record['document_id']}.")
        row = neo_props(record)
        row.setdefault('content_type', 'page_text')
        chunks[cid] = row
        texts[cid] = record['text']
        contains.append({'document_id': record['document_id'], 'chunk_id': cid})
        if is_figure:
            for parent in record.get('parent_chunk_ids', []):
                if parent not in page_ids:
                    problems.append(f'Suplemento {cid}: trecho-pai inexistente {parent}.')
                supplements.append({'chunk_id': cid, 'parent_id': parent})

    concepts = merge_concepts(extractions, problems)
    relations = merge_relations(extractions)
    mentions = set()
    for cid, m in concepts.items():
        check_evidence(f'Conceito {cid}', m['evidence'], texts, problems)
        mentions.update((e['chunk_id'], cid) for e in m['evidence'])
    by_type = OrderedDict((t, []) for t in ALLOWED_RELATION_TYPES)
    triples = []
    for (source, rtype, target), m in relations.items():
        owner = f'Relação {source} -[{rtype}]-> {target}'
        if rtype not in ALLOWED_RELATION_TYPES:
            problems.append(f'{owner}: tipo fora da lista permitida.')
        for end in (source, target):
            if end not in concepts:
                problems.append(f'{owner}: conceito inexistente {end}.')
        check_evidence(owner, m['evidence'], texts, problems)  # segue checando: reporta tudo de uma vez
        for e in m['evidence']:
            mentions.update([(e['chunk_id'], source), (e['chunk_id'], target)])
        if rtype in ALLOWED_RELATION_TYPES:
            by_type[rtype].append({'source': source, 'target': target, 'props': relation_props(m)})
            triples.append({'source': source, 'type': rtype, 'target': target})

    if problems:
        raise IngestError(f'{len(problems)} problema(s) encontrado(s); nada foi gravado:\n- ' + '\n- '.join(problems))
    return {
        'release': release['release'],
        'files': [e['path'] for e in extractions],
        'documents': list(documents.values()),
        'chunks': list(chunks.values()),
        'contains': contains,
        'supplements': supplements,
        'concepts': [concept_row(m) for m in concepts.values()],
        'mentions': [{'chunk_id': c, 'concept_id': k} for c, k in sorted(mentions)],
        'relations': OrderedDict((t, rows) for t, rows in by_type.items() if rows),
        'triples': triples,
    }


def expected_counts(payload):
    return OrderedDict([
        ('Document', len(payload['documents'])), ('Chunk', len(payload['chunks'])),
        ('Concept', len(payload['concepts'])), ('CONTAINS', len(payload['contains'])),
        ('SUPPLEMENTS', len(payload['supplements'])), ('MENTIONS', len(payload['mentions'])),
        ('semantic', sum(len(rows) for rows in payload['relations'].values())),
    ])


# ---------------------------------------------------------------- gravação

Q_DOCUMENT = ('UNWIND $rows AS row MERGE (n:Document {document_id: row.document_id}) '
              'SET n += row RETURN count(n) AS n')
Q_CHUNK = ('UNWIND $rows AS row MERGE (n:Chunk {chunk_id: row.chunk_id}) '
           'SET n += row RETURN count(n) AS n')
Q_CONCEPT = ('UNWIND $rows AS row MERGE (n:Concept {concept_id: row.concept_id}) '
             'SET n += row RETURN count(n) AS n')
Q_CONTAINS = ('UNWIND $rows AS row MATCH (d:Document {document_id: row.document_id}) '
              'MATCH (c:Chunk {chunk_id: row.chunk_id}) MERGE (d)-[r:CONTAINS]->(c) RETURN count(r) AS n')
Q_SUPPLEMENTS = ('UNWIND $rows AS row MATCH (f:Chunk {chunk_id: row.chunk_id}) '
                 'MATCH (p:Chunk {chunk_id: row.parent_id}) MERGE (f)-[r:SUPPLEMENTS]->(p) RETURN count(r) AS n')
Q_MENTIONS = ('UNWIND $rows AS row MATCH (c:Chunk {chunk_id: row.chunk_id}) '
              'MATCH (k:Concept {concept_id: row.concept_id}) MERGE (c)-[r:MENTIONS]->(k) RETURN count(r) AS n')
Q_SEMANTIC = ('UNWIND $rows AS row MATCH (s:Concept {{concept_id: row.source}}) '
              'MATCH (t:Concept {{concept_id: row.target}}) MERGE (s)-[r:{rel_type}]->(t) '
              'SET r += row.props RETURN count(r) AS n')


def write_payload(tx, payload):
    steps = [
        ('Document', Q_DOCUMENT, payload['documents']),
        ('Chunk', Q_CHUNK, payload['chunks']),
        ('Concept', Q_CONCEPT, payload['concepts']),
        ('CONTAINS', Q_CONTAINS, payload['contains']),
        ('SUPPLEMENTS', Q_SUPPLEMENTS, payload['supplements']),
        ('MENTIONS', Q_MENTIONS, payload['mentions']),
    ]
    for rel_type, rows in payload['relations'].items():
        if rel_type not in ALLOWED_RELATION_TYPES:  # defesa extra contra injeção de Cypher
            raise IngestError(f'Tipo de relação não permitido: {rel_type}')
        steps.append((rel_type, Q_SEMANTIC.format(rel_type=rel_type), rows))
    for label, query, rows in steps:
        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start:start + BATCH_SIZE]
            written = tx.run(query, rows=batch).single()['n']
            if written != len(batch):
                raise IngestError(f'{label}: esperava gravar {len(batch)} e gravou {written}; '
                                  f'há referência para nó inexistente. Nada foi salvo.')


def apply_schema(session):
    lines = [ln for ln in SCHEMA_FILE.read_text(encoding='utf-8').splitlines() if not ln.strip().startswith('//')]
    statements = [s.strip() for s in '\n'.join(lines).split(';') if s.strip()]
    for statement in statements:
        session.run(statement).consume()
    return len(statements)


# -------------------------------------------------------------- verificação

def verify(session, payload):
    """Devolve lista de (ok, descrição). Compara o banco com o que a carga deveria produzir."""
    results = []

    def check(ok, text):
        results.append((bool(ok), text))

    expected = expected_counts(payload)
    for label in ('Document', 'Chunk', 'Concept'):
        got = session.run(f'MATCH (n:{label}) RETURN count(n) AS n').single()['n']
        check(got == expected[label], f'{label}: {got} no banco, {expected[label]} esperados')
    for rel in ('CONTAINS', 'SUPPLEMENTS', 'MENTIONS'):
        got = session.run(f'MATCH ()-[r:{rel}]->() RETURN count(r) AS n').single()['n']
        check(got == expected[rel], f'{rel}: {got} no banco, {expected[rel]} esperados')
    types = list(ALLOWED_RELATION_TYPES)
    in_db = {r['t']: r['n'] for r in session.run(
        'MATCH ()-[r]->() WHERE type(r) IN $types RETURN type(r) AS t, count(r) AS n', types=types)}
    want = {t: len(rows) for t, rows in payload['relations'].items()}
    check(in_db == want, f'Relações semânticas por tipo: banco {in_db}, esperado {want}')

    for label, key, rows in (('Document', 'document_id', payload['documents']),
                             ('Chunk', 'chunk_id', payload['chunks']),
                             ('Concept', 'concept_id', payload['concepts'])):
        db_ids = set(session.run(f'MATCH (n:{label}) RETURN collect(n.{key}) AS ids').single()['ids'])
        want_ids = {r[key] for r in rows}
        check(db_ids == want_ids, f'{label}: IDs do banco = IDs da carga'
              + ('' if db_ids == want_ids else f' (a mais no banco: {sorted(db_ids - want_ids)[:5]}, '
                                               f'faltando: {sorted(want_ids - db_ids)[:5]})'))

    names = {r['name'] for r in session.run('SHOW CONSTRAINTS YIELD name RETURN name')}
    check(set(REQUIRED_CONSTRAINTS) <= names, f'Restrições de unicidade presentes: {sorted(set(REQUIRED_CONSTRAINTS) & names)}')
    state = {r['name']: r['state'] for r in session.run('SHOW INDEXES YIELD name, state RETURN name, state')}
    bad = [i for i in REQUIRED_INDEXES if state.get(i) != 'ONLINE']
    check(not bad, 'Índices ONLINE: ' + ('todos' if not bad else f'faltando/offline: {bad}'))

    got = session.run(
        'UNWIND $triples AS t MATCH (s:Concept {concept_id: t.source})-[r]->(k:Concept {concept_id: t.target}) '
        'WHERE type(r) = t.type RETURN count(r) AS n', triples=payload['triples']).single()['n']
    check(got == len(payload['triples']), f"Triplas (origem, tipo, destino) encontradas: {got} de {len(payload['triples'])}")
    no_evidence = session.run(
        'MATCH ()-[r]->() WHERE type(r) IN $types AND (r.evidence_chunk_ids IS NULL OR size(r.evidence_chunk_ids) = 0) '
        'RETURN count(r) AS n', types=types).single()['n']
    check(no_evidence == 0, f'Relações semânticas sem evidência: {no_evidence}')
    broken = session.run(
        'MATCH ()-[r]->() WHERE type(r) IN $types UNWIND r.evidence_chunk_ids AS cid '
        'OPTIONAL MATCH (c:Chunk {chunk_id: cid}) WITH r, cid, c WHERE c IS NULL RETURN count(*) AS n',
        types=types).single()['n']
    check(broken == 0, f'Evidências de relações apontando para Chunk inexistente: {broken}')
    fk_requires = session.run(
        "MATCH (:Concept {concept_id: 'C_join'})-[r:REQUIRES]->(:Concept {concept_id: 'C_foreign_key'}) "
        'RETURN count(r) AS n').single()['n']
    check(fk_requires == 0, 'Não existe aresta dizendo que JOIN exige chave estrangeira (FK só é "tipicamente usada")')
    two_hops = session.run(
        'MATCH (a:Concept)-[r1]->(b:Concept)-[r2]->(c:Concept) '
        'WHERE type(r1) IN $types AND type(r2) IN $types AND a <> c '
        'RETURN a.concept_id AS a, type(r1) AS t1, b.concept_id AS b, type(r2) AS t2, c.concept_id AS c, '
        'r1.evidence_chunk_ids AS e1, r2.evidence_chunk_ids AS e2 ORDER BY a, b, c', types=types).data()
    check(len(two_hops) >= 1, f'Caminhos de 2 saltos com evidência por aresta: {len(two_hops)}')
    for h in two_hops[:3]:
        results.append((True, f"    {h['a']} -[{h['t1']}]-> {h['b']} -[{h['t2']}]-> {h['c']}   evidências {h['e1']} + {h['e2']}"))
    return results


# ---------------------------------------------------------------- conexão e CLI

def connect(wait):
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / '.env')
    except ImportError:
        pass
    password = os.environ.get('NEO4J_PASSWORD')
    if not password:
        raise IngestError('NEO4J_PASSWORD não definida. Copie .env.example para .env e preencha a senha.')
    try:
        from neo4j import GraphDatabase
    except ImportError:
        raise IngestError('Driver ausente. Rode: python -m pip install -r requirements-neo4j.txt')
    uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    driver = GraphDatabase.driver(uri, auth=(os.environ.get('NEO4J_USER', 'neo4j'), password))
    deadline = time.time() + wait
    while True:
        try:
            driver.verify_connectivity()
            return driver
        except Exception as exc:  # o banco pode ainda estar iniciando
            if time.time() > deadline:
                driver.close()
                raise IngestError(f'Não consegui conectar em {uri} em {wait}s: {exc}\n'
                                  'O Neo4j está rodando? (docker compose up -d)')
            time.sleep(2)


def print_counts(payload):
    print('Carga (release ' + payload['release'] + '): ' + ', '.join(f'{k}={v}' for k, v in expected_counts(payload).items()))
    print('Arquivos: ' + ', '.join(payload['files']))


def print_results(results):
    for ok, text in results:
        print(('  [OK]    ' if ok else '  [FALHA] ') + text if not text.startswith('    ') else text)
    return all(ok for ok, _ in results)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('schema', help='cria restrições e índices (idempotente)')
    for name, help_text in (('ingest', 'grava a carga e verifica'), ('verify', 'confere o banco contra a carga')):
        p = sub.add_parser(name, help=help_text)
        p.add_argument('--include-sample', action='store_true',
                       help='inclui data/extraction/sample.json (opcional; traz o caminho FK→JOIN→outer join)')
        p.add_argument('--no-hash-check', action='store_true', help='não confere os hashes do índice da release')
    ingest = sub.choices['ingest']
    ingest.add_argument('--dry-run', action='store_true', help='valida e mostra contagens, sem acessar o banco')
    ingest.add_argument('--no-verify', action='store_true', help='não roda a verificação após gravar')
    for p in sub.choices.values():
        p.add_argument('--wait', type=int, default=60, help='segundos esperando o Neo4j subir (padrão 60)')
    args = parser.parse_args(argv)

    try:
        if args.command == 'schema':
            driver = connect(args.wait)
            with driver, driver.session(database=os.environ.get('NEO4J_DATABASE', 'neo4j')) as session:
                print(f'Esquema aplicado: {apply_schema(session)} comandos (restrições e índices).')
            return 0
        payload = build_payload(ROOT, args.include_sample, not args.no_hash_check)
        print_counts(payload)
        if args.command == 'ingest' and args.dry_run:
            print('Dry-run: dados válidos, nada foi gravado.')
            return 0
        driver = connect(args.wait)
        with driver, driver.session(database=os.environ.get('NEO4J_DATABASE', 'neo4j')) as session:
            if args.command == 'ingest':
                session.execute_write(write_payload, payload)
                print('Carga gravada em uma transação.')
                if args.no_verify:
                    return 0
            print('Verificação:')
            return 0 if print_results(verify(session, payload)) else 1
    except IngestError as exc:
        print(f'ERRO: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
