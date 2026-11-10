"""Export only explicitly reviewed batch proposals into the existing graph contract."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def normalize(s):
    return ' '.join(html.unescape(re.sub('<[^>]+>', '', s)).casefold().split())


def export(batch, review, chunks, relation_registry=None):
    if review.get('batch_sha256'):
        digest = hashlib.sha256(json.dumps(batch, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
        if digest != review['batch_sha256']:
            raise ValueError('Batch changed after review; review it again before exporting.')
    runs = {r['passage_id']: r for r in batch['runs']}
    concepts, relations, seen = {}, {}, set()
    known_relations = {(r['source'], r['type'], r['target']): r['relation_id']
                       for r in (relation_registry or [])}
    definitions = review['concepts']
    for decision in review['decisions']:
        pid = decision['passage_id']
        if pid in seen:
            raise ValueError('Duplicate review decision.')
        seen.add(pid)
        if pid not in runs:
            raise ValueError('Review references an absent passage.')
        if not decision.get('note', '').strip():
            raise ValueError('Every review decision requires a note.')
        if decision['decision'] != 'accept':
            if decision['decision'] not in ('reject', 'flag'):
                raise ValueError('Unknown review action.')
            continue
        run = runs[pid]
        if run.get('is_synthetic_control') or run['status'] != 'passed_model_check_pending_review':
            raise ValueError('Only real, structurally validated proposals may be exported by this command.')
        if len(run['relations']) != 1:
            raise ValueError('Expected exactly one proposal.')
        r = run['relations'][0]
        if decision.get('expected_type') != r['type']:
            raise ValueError('Reviewed predicate differs from the proposal.')
        e = r['evidence']
        if chunks[e['chunk_id']]['text'][e['start']:e['end']] != e['quote']:
            raise ValueError('Evidence offsets do not reproduce source text.')
        ids = []
        for endpoint in ('source', 'target'):
            cid = decision[endpoint + '_concept_id']
            c = definitions[cid]
            labels = [c['canonical_name'], c['name_pt']] + c['aliases']
            if normalize(r[endpoint]) not in {normalize(label) for label in labels}:
                raise ValueError('Reviewed mapping must preserve the original surface as name or alias.')
            if cid not in concepts:
                concepts[cid] = {'concept_id': cid, **c, 'evidence': [], 'review_status': 'accepted',
                    'review_note': 'Model proposal reviewed by Codex; names and translations curated. No independent human review.'}
            quote = {k: e[k] for k in ('chunk_id', 'quote')}
            if quote not in concepts[cid]['evidence']:
                concepts[cid]['evidence'].append(quote)
            ids.append(cid)
        key = (ids[0], r['type'], ids[1])
        if key not in relations:
            digest = hashlib.sha256('|'.join(key).encode()).hexdigest()[:16]
            relations[key] = {'relation_id': known_relations.get(key, 'R_batch_' + digest), 'source': ids[0], 'type': r['type'],
                'target': ids[1], 'assertion_kind': 'explicit', 'evidence': [],
                'review_status': 'accepted', 'review_note': decision['note']}
        quote = {k: e[k] for k in ('chunk_id', 'quote')}
        if quote not in relations[key]['evidence']:
            relations[key]['evidence'].append(quote)
    if seen != set(runs):
        raise ValueError('Review must account for every processed passage, including exclusions and controls.')
    if not concepts:
        raise ValueError('No approved knowledge to export.')
    sql_types = {'RETRIEVES', 'FILTERS', 'GROUPS', 'AGGREGATES', 'EVALUATED_BEFORE', 'REMOVES_DUPLICATES'}
    version = '0.1.2' if any(r['type'] in sql_types for r in relations.values()) else '0.1.0'
    return {'schema_version': version, 'extraction_method': 'llm_candidates',
            'input_chunk_ids': sorted({e['chunk_id'] for c in concepts.values() for e in c['evidence']}),
            'concepts': list(concepts.values()), 'relations': list(relations.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base', type=Path, default=ROOT / 'data/extraction/sample.json',
                        help='Preserve known relation IDs for equal canonical triples; no base facts are copied.')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        parser.error('Choose a new output file inside the project.')
    chunks = {}
    for name in ('chunks.jsonl', 'figure_supplements.jsonl'):
        for line in (ROOT / 'corpus/chunks' / name).read_text(encoding='utf-8').splitlines():
            if line.strip():
                c = json.loads(line)
                chunks[c['chunk_id']] = c
    result = export(json.loads(args.batch.read_text(encoding='utf-8')),
                    json.loads(args.review.read_text(encoding='utf-8')), chunks,
                    json.loads(args.base.read_text(encoding='utf-8-sig'))['relations'])
    schema = json.loads((ROOT / 'schemas/extraction.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(schema).validate(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Exported {len(result['concepts'])} reviewed concepts and {len(result['relations'])} relations.")


if __name__ == '__main__':
    main()
