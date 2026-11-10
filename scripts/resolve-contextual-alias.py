"""Resolve source cross-references with document scope; never merge graph nodes."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def normalize(value):
    return ' '.join(value.casefold().split())


def load_registry(root=ROOT):
    registry = json.loads((root / 'data/normalization/contextual-aliases-v1.json').read_text(encoding='utf-8'))
    for item in registry['protected_files']:
        source = (root / item['path']).resolve()
        if not source.is_relative_to(root.resolve()):
            raise ValueError('Registry path leaves the project.')
        if hashlib.sha256(source.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Registry input changed; review it again: ' + item['path'])
    chunks = {}
    for name in ('chunks.jsonl', 'figure_supplements.jsonl'):
        for line in (root / 'corpus/chunks' / name).read_text(encoding='utf-8').splitlines():
            if line.strip():
                chunk = json.loads(line)
                chunks[chunk['chunk_id']] = chunk
    valid_ids = set()
    for path in registry['concept_files']:
        valid_ids.update(c['concept_id'] for c in json.loads((root / path).read_text(encoding='utf-8'))['concepts'])
    seen = set()
    for entry in registry['entries']:
        if entry['id'] in seen or not entry['forms'] or entry['auto_merge_nodes'] is not False:
            raise ValueError('Invalid contextual rule.')
        seen.add(entry['id'])
        if entry['action'] not in ('contextual_reference', 'requires_review'):
            raise ValueError('Unknown contextual action.')
        if entry['action'] == 'contextual_reference' and not entry['reference_concept_ids']:
            raise ValueError('Cross-reference has no target.')
        if set(entry['reference_concept_ids']) - valid_ids:
            raise ValueError('Unknown reference concept.')
        if not entry['document_ids'] or not entry['note'].strip() or not entry['evidence']:
            raise ValueError('Context and evidence are mandatory.')
        for evidence in entry['evidence']:
            chunk = chunks[evidence['chunk_id']]
            if chunk['document_id'] not in entry['document_ids']:
                raise ValueError('Evidence outside document scope.')
            if evidence['start'] < 0 or evidence['end'] <= evidence['start'] or chunk['text'][evidence['start']:evidence['end']] != evidence['quote']:
                raise ValueError('Nonliteral contextual evidence.')
    return registry, chunks


def resolve(term, registry, chunks, document_id=None, chunk_id=None):
    if chunk_id:
        if chunk_id not in chunks:
            raise ValueError('Unknown chunk.')
        inferred_document = chunks[chunk_id]['document_id']
        if document_id and document_id != inferred_document:
            raise ValueError('Document and chunk refer to different sources.')
        document_id = inferred_document
    if document_id and document_id not in {chunk['document_id'] for chunk in chunks.values()}:
        raise ValueError('Unknown document.')
    matches = [entry for entry in registry['entries'] if normalize(term) in {normalize(form) for form in entry['forms']}]
    result = dict(term=term, document_id=document_id, chunk_id=chunk_id,
                  status='no_match', reference_concept_ids=[], auto_merge_nodes=False, references=[])
    if not matches:
        return result
    if not document_id:
        result['status'] = 'requires_document_context'
        return result
    for entry in matches:
        if document_id not in entry['document_ids']:
            continue
        if entry.get('chunk_ids') and not chunk_id:
            result['status'] = 'requires_chunk_context'
            return result
        if entry.get('chunk_ids') and chunk_id not in entry['chunk_ids']:
            continue
        result['references'].append(entry)
    if result['references']:
        if any(entry['action'] == 'requires_review' for entry in result['references']):
            result['status'] = 'requires_review'
        else:
            result['status'] = 'contextual_reference'
            result['reference_concept_ids'] = sorted({cid for entry in result['references'] for cid in entry['reference_concept_ids']})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--term', required=True)
    parser.add_argument('--document')
    parser.add_argument('--chunk')
    args = parser.parse_args()
    registry, chunks = load_registry()
    try:
        result = resolve(args.term, registry, chunks, args.document, args.chunk)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
