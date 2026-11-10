"""Export source glossary concepts only after explicit, exhaustive review decisions."""
import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def export(entries, review, chunks):
    candidates = {e['candidate_id']: e for e in entries}
    if len(candidates) != len(entries):
        raise ValueError('Duplicate candidate IDs.')
    seen, concepts = set(), {}
    for decision in review['decisions']:
        cid = decision['candidate_id']
        if cid not in candidates or cid in seen:
            raise ValueError('Unknown or duplicate review decision.')
        seen.add(cid)
        if not decision['note'].strip():
            raise ValueError('Review rationale required.')
        if decision['decision'] != 'accept':
            if decision['decision'] not in ('flag', 'exclude'):
                raise ValueError('Unknown action.')
            continue
        e = candidates[cid]
        if chunks[e['chunk_id']]['text'][e['start']:e['end']] != e['quote']:
            raise ValueError('Quote does not match source offsets.')
        concept_id = decision['concept_id']
        definition = review['concepts'][concept_id]
        if e['surface'].casefold() not in {s.casefold() for s in [definition['canonical_name']] + definition['aliases']}:
            raise ValueError('Original surface must be preserved as canonical name or alias.')
        if concept_id not in concepts:
            concepts[concept_id] = {'concept_id': concept_id, **definition, 'evidence': [],
                'review_status': 'accepted', 'review_note': review.get('review_note', 'Source glossary extraction by rules; concept naming, Portuguese summaries and scope reviewed by Codex. No independent human review.')}
        evidence = {'chunk_id': e['chunk_id'], 'quote': e['quote']}
        if evidence not in concepts[concept_id]['evidence']:
            concepts[concept_id]['evidence'].append(evidence)
        concepts[concept_id]['review_note'] += '\n' + decision['note']
    if seen != set(candidates):
        raise ValueError('Every candidate needs an explicit review decision.')
    if not concepts:
        raise ValueError('No concepts approved.')
    return {'schema_version': '0.1.1', 'extraction_method': 'rule_candidates',
            'input_chunk_ids': sorted({e['chunk_id'] for c in concepts.values() for e in c['evidence']}),
            'concepts': sorted(concepts.values(), key=lambda c: c['concept_id']), 'relations': []}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidates', type=Path, required=True)
    p.add_argument('--review', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not args.output.resolve().is_relative_to(ROOT) or args.output.exists():
        p.error('Choose a new output file inside project.')
    raw = args.candidates.read_bytes()
    review = json.loads(args.review.read_text(encoding='utf-8'))
    if hashlib.sha256(raw).hexdigest() != review['candidates_sha256']:
        raise ValueError('Candidates changed after review.')
    entries = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    chunks = {c['chunk_id']: c for c in (json.loads(line) for line in
        (ROOT / 'corpus/chunks/chunks.jsonl').read_text(encoding='utf-8').splitlines())}
    graph = export(entries, review, chunks)
    schema = json.loads((ROOT / 'schemas/extraction.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(schema).validate(graph)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Exported {len(graph['concepts'])} reviewed concepts, no semantic relationships generated.")


if __name__ == '__main__':
    main()
