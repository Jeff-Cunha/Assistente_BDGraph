"""Check that an answer stays inside its retrieved evidence and score documentary support.

The model never reports a confidence number: it only declares claims and the evidence
identifiers it used. This module rejects invented identifiers, drops or rejects claims
without evidence, resolves every citation to a chunk and a source URL, and derives a
support level from rules that can be read in the README instead of guessed.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

CHUNK_ID = re.compile(r'D[0-9]{2}_(?:C[0-9]{3}|F[0-9]{3}_S[0-9]{3})')
EVIDENCE_ID = re.compile(r'E[0-9]+')
REVIEW_STATUSES = ('accepted', 'pending', 'flagged')
ORIGINS = ('graph', 'vector', 'concept')
CHANNELS = ('vector', 'graph')

MODEL_RESPONSE_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['answered', 'answer_pt', 'claims', 'notes'],
    'properties': {
        'answered': {'type': 'boolean'},
        'answer_pt': {'type': 'string', 'minLength': 1},
        'claims': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['text', 'evidence_ids'],
                'properties': {
                    'text': {'type': 'string', 'minLength': 1},
                    'evidence_ids': {
                        'type': 'array', 'minItems': 1, 'uniqueItems': True,
                        'items': {'type': 'string', 'pattern': '^E[0-9]+$'},
                    },
                },
            },
        },
        'notes': {'type': 'string'},
    },
}

ABSTENTION_PT = ('Não há evidência suficiente nos trechos recuperados para responder a '
                 'esta pergunta com fontes verificáveis.')

SUPPORT_LIMITATION_PT = ('O nível de sustentação é uma regra sobre as evidências usadas '
                         'nesta resposta; não é uma probabilidade calibrada de acerto.')


class GroundingError(ValueError):
    """Raised when an answer, or the bundle it relies on, breaks the evidence contract."""


def _fail(message):
    raise GroundingError(message)


def load_corpus_texts(root=ROOT):
    """Map chunk_id to its stored text, read from the corpus without modifying it."""
    texts = {}
    for name in ('chunks.jsonl', 'figure_supplements.jsonl'):
        path = Path(root) / 'corpus' / 'chunks' / name
        if not path.exists():
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                row = json.loads(line)
                texts[row['chunk_id']] = row['text']
    return texts


def normalize_bundle(bundle):
    """Validate the retrieval hand-off and give every evidence item a stable identifier."""
    if not isinstance(bundle, dict):
        _fail('Bundle must be a JSON object.')
    question = bundle.get('question')
    if not isinstance(question, str) or not question.strip():
        _fail('Bundle needs a non-empty question.')
    evidence = bundle.get('evidence')
    if not isinstance(evidence, list) or not evidence:
        _fail('Bundle needs at least one evidence item.')
    retrieval = bundle.get('retrieval') or {}
    if not isinstance(retrieval, dict):
        _fail('Bundle retrieval must be an object.')
    channels = retrieval.get('channels', [])
    if not isinstance(channels, list) or any(c not in CHANNELS for c in channels):
        _fail(f'retrieval.channels accepts only {list(CHANNELS)}.')
    concepts = bundle.get('concepts') or []
    if not isinstance(concepts, list) or any(not isinstance(c, dict) for c in concepts):
        _fail('Bundle concepts must be a list of objects.')
    normalized, seen = [], set()
    for position, item in enumerate(evidence, 1):
        if not isinstance(item, dict):
            _fail(f'Evidence {position} must be an object.')
        chunk_id, quote = item.get('chunk_id'), item.get('quote')
        if not isinstance(chunk_id, str) or not CHUNK_ID.fullmatch(chunk_id):
            _fail(f'Invalid chunk_id in evidence {position}.')
        if not isinstance(quote, str) or not quote.strip():
            _fail(f'Evidence {position} needs a non-empty literal quote.')
        identifier = item.get('evidence_id') or f'E{position}'
        if not EVIDENCE_ID.fullmatch(identifier):
            _fail(f'Invalid evidence_id in evidence {position}.')
        if identifier in seen:
            _fail(f'Duplicate evidence_id: {identifier}.')
        seen.add(identifier)
        review = item.get('review_status', 'pending')
        if review not in REVIEW_STATUSES:
            _fail(f'Invalid review_status in evidence {position}.')
        origin = item.get('origin', 'vector')
        if origin not in ORIGINS:
            _fail(f'Invalid origin in evidence {position}.')
        relation = item.get('relation')
        if relation is not None and not isinstance(relation, dict):
            _fail(f'Evidence relation in {position} must be an object.')
        normalized.append({
            'evidence_id': identifier,
            'chunk_id': chunk_id,
            'document_id': item.get('document_id'),
            'title': item.get('title'),
            'source_url': item.get('source_url'),
            'section_path': item.get('section_path'),
            'quote': quote,
            'review_status': review,
            'origin': origin,
            'relation': relation,
        })
    return {
        'question': question.strip(),
        'language': bundle.get('language', 'pt-BR'),
        'retrieval': {
            'strategy': retrieval.get('strategy', 'hybrid'),
            'channels': list(channels),
            'graph_executed': bool(retrieval.get('graph_executed', False)),
            'max_hops': retrieval.get('max_hops'),
        },
        'concepts': concepts,
        'evidence': normalized,
    }


_MARKDOWN_ESCAPE = re.compile(r'\\([^A-Za-z0-9\s])')


def check_quotes(evidence, chunk_texts=None):
    """Annotate evidence with quote_verified: True, False, or None when the corpus is absent.
    Comparison only removes Markdown escapes that the exchange format added; the stored
    quote is never rewritten."""
    if not chunk_texts:
        return [dict(item, quote_verified=None) for item in evidence]
    checked = []
    for item in evidence:
        text = chunk_texts.get(item['chunk_id'])
        if text is None:
            verified = None
        elif item['quote'] in text:
            verified = True
        else:
            verified = _MARKDOWN_ESCAPE.sub(r'\1', item['quote']) in text
        checked.append(dict(item, quote_verified=verified))
    return checked


def verify_model_answer(raw, bundle):
    """Reject invented references and set aside claims that carry no evidence at all."""
    if not isinstance(raw, dict):
        _fail('Model response must be a JSON object.')
    unknown = sorted(set(raw) - set(MODEL_RESPONSE_SCHEMA['properties']))
    if unknown:
        _fail(f'Unexpected field(s) in model response: {unknown}.')
    missing = sorted(set(MODEL_RESPONSE_SCHEMA['required']) - set(raw))
    if missing:
        _fail(f'Missing field(s) in model response: {missing}.')
    if not isinstance(raw['answered'], bool):
        _fail('answered must be a boolean.')
    answer = raw['answer_pt']
    if not isinstance(answer, str) or not answer.strip():
        _fail('answer_pt must be a non-empty string.')
    claims = raw['claims']
    if not isinstance(claims, list):
        _fail('claims must be a list.')
    notes = raw.get('notes', '')
    if not isinstance(notes, str):
        _fail('notes must be a string.')
    if not raw['answered']:
        if claims:
            _fail('An abstention must not carry claims.')
        return {'answered': False, 'kept': [], 'dropped': [], 'notes': notes.strip(),
                'model_text': answer.strip()}
    index = {item['evidence_id'] for item in bundle['evidence']}
    kept, dropped = [], []
    for position, claim in enumerate(claims, 1):
        if not isinstance(claim, dict):
            _fail(f'Claim {position} must be an object.')
        text, ids = claim.get('text'), claim.get('evidence_ids')
        if not isinstance(text, str) or not text.strip():
            _fail(f'Claim {position} needs non-empty text.')
        if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
            _fail(f'Claim {position} needs an evidence_ids list.')
        outside = [item for item in ids if item not in index]
        if outside:
            _fail(f'Claim {position} cites evidence outside the bundle: {outside}.')
        if not ids:
            dropped.append({'text': text.strip(), 'reason': 'claim_without_evidence'})
            continue
        kept.append({'text': text.strip(), 'evidence_ids': list(ids)})
    if not claims:
        _fail('An answered response needs at least one claim.')
    return {'answered': True, 'answer_pt': answer.strip(), 'kept': kept, 'dropped': dropped,
            'notes': notes.strip(), 'model_text': None}


def score_support(claims, evidence, dropped=0):
    """Derive the support level from documentary rules; never from a model estimate."""
    used_ids = []
    for claim in claims:
        for identifier in claim['evidence_ids']:
            if identifier not in used_ids:
                used_ids.append(identifier)
    by_id = {item['evidence_id']: item for item in evidence}
    used = [by_id[identifier] for identifier in used_ids]
    documents = sorted({item['document_id'] for item in used if item['document_id']})
    chunks = sorted({item['chunk_id'] for item in used})
    unaccepted = [item['evidence_id'] for item in used if item['review_status'] != 'accepted']
    unverified = [item['evidence_id'] for item in used if item['quote_verified'] is False]
    considered = len(claims) + dropped
    coverage = len(claims) / considered if considered else 0.0
    reasons = []
    if not claims:
        level = 'insufficient'
        reasons.append('Nenhuma afirmação foi sustentada por evidência recuperada.')
    elif unaccepted or dropped:
        level = 'low'
        if unaccepted:
            reasons.append(f'{len(unaccepted)} citação(ões) pendente(s) ou sinalizada(s) na revisão.')
        if dropped:
            reasons.append(f'{dropped} afirmação(ões) foram descartadas por não citarem evidência.')
    elif len(chunks) < 2 or len(documents) < 2 or unverified:
        level = 'medium'
        if len(chunks) < 2:
            reasons.append('A resposta se apoia em um único trecho.')
        if len(documents) < 2:
            reasons.append('A resposta se apoia em um único documento.')
        if unverified:
            reasons.append(f'{len(unverified)} citação(ões) não conferida(s) contra o texto do trecho.')
    else:
        level = 'high'
    if claims:
        reasons.insert(0, f'{len(claims)} de {considered} afirmação(ões) citam evidência; '
                          f'{len(chunks)} trecho(s) de {len(documents)} documento(s).')
    return {
        'level': level,
        'coverage': round(coverage, 3),
        'claims_with_evidence': len(claims),
        'claims_without_evidence': dropped,
        'distinct_chunks': len(chunks),
        'distinct_documents': len(documents),
        'evidence_review': ('accepted' if used and not unaccepted else
                            'mixed' if used else 'none'),
        'unverified_quotes': len(unverified),
        'reasons': reasons,
    }


def _limitations(bundle, support, claims):
    """User-facing caveats, written so the interface can show why a level was assigned."""
    limitations = [SUPPORT_LIMITATION_PT]
    if claims and support['evidence_review'] == 'mixed':
        limitations.append('Parte das citações está pendente ou sinalizada na revisão de extração.')
    if claims and support['distinct_documents'] < 2:
        limitations.append('As evidências vêm de um único documento; generalizações exigem '
                           'conferência em outras fontes do corpus.')
    if claims and not bundle['retrieval']['graph_executed']:
        limitations.append('Nenhum caminho do grafo foi percorrido nesta resposta; as fontes '
                           'vêm apenas da recuperação textual.')
    if support['claims_without_evidence']:
        limitations.append('Afirmações sem evidência recuperada foram descartadas e não '
                           'fazem parte da resposta.')
    if support['unverified_quotes']:
        limitations.append('Uma ou mais citações não coincidem literalmente com o texto do '
                           'trecho no corpus local.')
    return limitations


def build_response(bundle, evidence, claims, dropped, answer_pt, support,
                   graph=None, model=None):
    """Assemble the object consumed by the interface, resolving every citation to a source."""
    by_id = {item['evidence_id']: item for item in evidence}
    used_ids = []
    for claim in claims:
        for identifier in claim['evidence_ids']:
            if identifier not in used_ids:
                used_ids.append(identifier)
    citations, sources = [], []
    for identifier in used_ids:
        item = by_id[identifier]
        citations.append({
            'evidence_id': identifier,
            'chunk_id': item['chunk_id'],
            'document_id': item['document_id'],
            'title': item['title'],
            'source_url': item['source_url'],
            'section_path': item['section_path'],
            'quote': item['quote'],
            'review_status': item['review_status'],
            'origin': item['origin'],
            'quote_verified': item['quote_verified'],
        })
        source = next((row for row in sources if row['document_id'] == item['document_id']), None)
        if source is None:
            source = {'document_id': item['document_id'], 'title': item['title'],
                      'source_url': item['source_url'], 'chunk_ids': []}
            sources.append(source)
        if item['chunk_id'] not in source['chunk_ids']:
            source['chunk_ids'].append(item['chunk_id'])
    response = {
        'schema_version': '0.1.0',
        'question': bundle['question'],
        'answered': bool(claims),
        'answer_pt': answer_pt,
        'claims': claims,
        'dropped_claims': dropped,
        'citations': citations,
        'sources': sources,
        'support': support,
        'limitations': _limitations(bundle, support, claims),
    }
    if graph is not None:
        response['graph'] = graph
    if model is not None:
        response['model'] = model
    return response


def abstention(bundle, reason, dropped=None, graph=None, model=None):
    """Refuse to answer when no evidence survived verification."""
    support = {
        'level': 'insufficient', 'coverage': 0.0, 'claims_with_evidence': 0,
        'claims_without_evidence': len(dropped or []), 'distinct_chunks': 0,
        'distinct_documents': 0, 'evidence_review': 'none', 'unverified_quotes': 0,
        'reasons': [reason],
    }
    return build_response(bundle, bundle['evidence'], [], list(dropped or []),
                          ABSTENTION_PT, support, graph, model)


def evaluate(bundle, raw, chunk_texts=None, graph=None, model=None):
    """Full pipeline: normalise the bundle, verify the model answer, score support, assemble."""
    bundle = normalize_bundle(bundle)
    evidence = check_quotes(bundle['evidence'], chunk_texts)
    if raw is None:
        return abstention(bundle, 'Nenhuma resposta foi gerada para esta pergunta.', graph=graph)
    verified = verify_model_answer(raw, bundle)
    if not verified['answered']:
        return abstention(bundle, f'O modelo declarou falta de evidência: {verified["model_text"]}',
                          graph=graph, model=model)
    if not verified['kept']:
        return abstention(bundle, 'Todas as afirmações foram descartadas por não citarem evidência.',
                          dropped=verified['dropped'], graph=graph, model=model)
    support = score_support(verified['kept'], evidence, dropped=len(verified['dropped']))
    return build_response(bundle, evidence, verified['kept'], verified['dropped'],
                          verified['answer_pt'], support, graph, model)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--response', type=Path, help='Model response JSON; omit to abstain.')
    parser.add_argument('--no-corpus', action='store_true',
                        help='Skip literal quote checking against corpus/chunks.')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_text(encoding='utf-8'))
    raw = json.loads(args.response.read_text(encoding='utf-8')) if args.response else None
    chunk_texts = None if args.no_corpus else load_corpus_texts()
    try:
        result = evaluate(bundle, raw, chunk_texts)
    except GroundingError as exc:
        print(f'REJECTED: {exc}')
        raise SystemExit(1)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
