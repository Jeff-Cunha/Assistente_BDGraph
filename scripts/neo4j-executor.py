"""Run the compiled read-only Cypher against Neo4j and turn the resulting paths into evidence.

Every statement goes through guard-cypher before it is sent, and through execute_query with
RoutingControl.READ, so the Community server refuses writes even if the guard misses something.
The password is read from the environment or a local .env and is never logged.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('guard_cypher', ROOT / 'scripts/guard-cypher.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

CONFIG_KEYS = ('NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD', 'NEO4J_DATABASE')
DEFAULT_URI = 'bolt://localhost:7687'
DEFAULT_USER = 'neo4j'
DEFAULT_DATABASE = 'neo4j'
DEFAULT_TIMEOUT = 10.0

Q_CHUNK_META = (
    'MATCH (c:Chunk) WHERE c.chunk_id IN $chunk_ids '
    'OPTIONAL MATCH (d:Document)-[:CONTAINS]->(c) '
    'RETURN c.chunk_id AS chunk_id, c.document_id AS document_id, c.source_url AS source_url, '
    'c.section_path AS section_path, d.title AS title LIMIT $limit')


class ExecutorError(RuntimeError):
    """Raised when the database cannot be reached, configured or trusted."""


def load_config(root=ROOT):
    """Read NEO4J_* from the environment, falling back to a local .env with simple key=value lines."""
    values = {}
    path = Path(root) / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, separator, value = line.partition('=')
            if separator and key.strip() in CONFIG_KEYS:
                values[key.strip()] = value.strip().strip('"\'')
    config = {key: os.environ.get(key, values.get(key, '')) for key in CONFIG_KEYS}
    config['NEO4J_URI'] = config['NEO4J_URI'] or DEFAULT_URI
    config['NEO4J_USER'] = config['NEO4J_USER'] or DEFAULT_USER
    config['NEO4J_DATABASE'] = config['NEO4J_DATABASE'] or DEFAULT_DATABASE
    if not config['NEO4J_PASSWORD']:
        raise ExecutorError('Configure NEO4J_PASSWORD no ambiente ou no .env local; '
                            'a senha não é lida do repositório.')
    return config


def redact(config):
    """Safe description for logs and error messages: never the password."""
    return {'uri': config['NEO4J_URI'], 'user': config['NEO4J_USER'],
            'database': config['NEO4J_DATABASE'], 'password': '***'}


def connect(config):
    """Open a driver and fail loudly, without echoing credentials."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        raise ExecutorError('Driver neo4j ausente. Instale requirements-neo4j.txt (parte 2): '
                            'python -m pip install -r requirements-neo4j.txt') from None
    try:
        driver = GraphDatabase.driver(config['NEO4J_URI'],
                                      auth=(config['NEO4J_USER'], config['NEO4J_PASSWORD']))
        driver.verify_connectivity()
    except Exception as exc:
        raise ExecutorError(f'Não foi possível conectar em {config["NEO4J_URI"]}: '
                            f'{type(exc).__name__}. Confira se o Neo4j está no ar e se o .env está correto.') from None
    return driver


def read_rows(driver, query, parameters, database, timeout=DEFAULT_TIMEOUT):
    """Execute one statement with READ routing, a server-side timeout and dict rows."""
    from neo4j import RoutingControl
    from neo4j.exceptions import Neo4jError
    try:
        return driver.execute_query(
            query, parameters, routing_=RoutingControl.READ, database_=database,
            timeout=timeout, result_transformer_=lambda result: [row.data() for row in result])
    except Neo4jError as exc:
        if exc.code == 'Neo.ClientError.Statement.AccessMode':
            raise ExecutorError('O banco recusou a consulta por ser somente leitura; '
                                'nenhuma geração deve produzir escrita.') from None
        raise ExecutorError(f'Consulta rejeitada pelo Neo4j: {exc.code}.') from None


def execute_plan(driver, plan, database, timeout=DEFAULT_TIMEOUT, max_hops=4, max_limit=200):
    """Compile a validated plan, then execute it as a read-only statement."""
    compiled = guard.compile_plan(plan, max_hops=max_hops, max_limit=max_limit)
    rows = read_rows(driver, compiled['cypher'], compiled['parameters'], database, timeout)
    return {'cypher': compiled['cypher'], 'parameters': compiled['parameters'], 'rows': rows}


def chunk_metadata(driver, chunk_ids, database, timeout=DEFAULT_TIMEOUT, max_limit=200):
    """Resolve chunk and document attributes for the evidence returned by a path query."""
    identifiers = sorted(set(chunk_ids))
    if not identifiers:
        return {}
    if len(identifiers) > max_limit:
        raise ExecutorError(f'{len(identifiers)} trechos de evidência; o limite é {max_limit}.')
    parameters = {'chunk_ids': identifiers, 'limit': len(identifiers)}
    checked = guard.validate_cypher(Q_CHUNK_META, parameters, max_limit=max_limit)
    rows = read_rows(driver, checked['query'], checked['parameters'], database, timeout)
    return {row['chunk_id']: row for row in rows}


def evidence_chunk_ids(rows):
    """Chunk identifiers cited by the relationships of the returned paths, without duplicates."""
    identifiers = []
    for row in rows:
        for relationship in row.get('relationships') or []:
            if isinstance(relationship, dict):
                for chunk_id in relationship.get('evidence_chunk_ids') or []:
                    if chunk_id not in identifiers:
                        identifiers.append(chunk_id)
    return identifiers


def bundle_from_paths(question, rows, metadata, language='pt-BR'):
    """Map path rows to the evidence bundle answer-grounding consumes.

    Quotes come from the stored evidence of each relationship and are never rewritten, so a
    translation or a paraphrase can never be presented as a source."""
    evidence, seen, concepts, hops = [], set(), [], 0
    for row in rows:
        nodes = row.get('nodes') or []
        relationships = row.get('relationships') or []
        hops = max(hops, len(relationships))
        for node in nodes:
            if isinstance(node, dict) and node.get('label') == 'Concept':
                concept = {'concept_id': node.get('id'),
                           'canonical_name': node.get('canonical_name'),
                           'name_pt': node.get('name_pt')}
                if concept['concept_id'] and concept not in concepts:
                    concepts.append(concept)
        for relationship in relationships:
            if not isinstance(relationship, dict):
                continue        # compiled without evidence: only the relationship type is known
            try:
                quotes = json.loads(relationship.get('evidence_quotes_json') or '[]')
            except json.JSONDecodeError:
                owner = relationship.get('relation_id') or relationship.get('type')
                raise ExecutorError(f'Evidência armazenada sem JSON válido em {owner}.') from None
            for item in quotes:
                chunk_id = (item or {}).get('chunk_id')
                quote = (item or {}).get('quote')
                if not chunk_id or not quote:
                    raise ExecutorError('Evidência armazenada sem chunk_id ou citação literal.')
                if (chunk_id, quote) in seen:
                    continue
                seen.add((chunk_id, quote))
                meta = metadata.get(chunk_id) or {}
                evidence.append({
                    'chunk_id': chunk_id,
                    'document_id': meta.get('document_id'),
                    'title': meta.get('title'),
                    'source_url': meta.get('source_url'),
                    'section_path': meta.get('section_path'),
                    'quote': quote,
                    'review_status': relationship.get('review_status') or 'pending',
                    'origin': 'graph',
                    'relation': {'relation_id': relationship.get('relation_id'),
                                 'type': relationship.get('type'),
                                 'source': relationship.get('source'),
                                 'target': relationship.get('target')},
                })
    return {
        'question': question,
        'language': language,
        'retrieval': {'strategy': 'graph', 'channels': ['graph'], 'graph_executed': True,
                      'max_hops': hops},
        'concepts': concepts,
        'evidence': evidence,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--question', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'work/graph-bundle.json')
    parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument('--max-hops', type=int, default=4)
    parser.add_argument('--check', action='store_true',
                        help='Only verify connectivity and node counts; no bundle is written.')
    args = parser.parse_args()
    if args.timeout <= 0 or args.max_hops <= 0:
        parser.error('Numeric limits must be positive.')
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    try:
        config = load_config()
        driver = connect(config)
        try:
            database = config['NEO4J_DATABASE']
            if args.check:
                for label in sorted(guard.ALLOWED_LABELS):
                    checked = guard.validate_cypher(f'MATCH (n:{label}) RETURN count(n) AS n', {})
                    rows = read_rows(driver, checked['query'], checked['parameters'],
                                     database, args.timeout)
                    print(f'{label}: {rows[0]["n"]}')
                print(f'Conexão OK em {config["NEO4J_URI"]} (banco {database}).')
                return
            executed = execute_plan(driver, plan, database, args.timeout, args.max_hops)
            metadata = chunk_metadata(driver, evidence_chunk_ids(executed['rows']),
                                      database, args.timeout)
        finally:
            driver.close()
    except (ExecutorError, guard.InvalidPlan, guard.UnsafeCypher) as exc:
        print(f'FAILED: {exc}')
        raise SystemExit(1)
    bundle = bundle_from_paths(args.question, executed['rows'], metadata)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(executed["rows"])} caminho(s), {len(bundle["evidence"])} evidência(s), '
          f'{len(bundle["concepts"])} conceito(s) -> {args.output}')
    if not bundle['evidence']:
        print('Sem evidência recuperada: o adaptador vai abster-se em vez de responder.')


if __name__ == '__main__':
    main()
