"""Apply a hash-bound source review to new outputs, retaining historical extractions."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Review paths must remain inside the project.')
    return path


def validate_graph(graph, chunks, validator):
    validator.validate(graph)
    ids = [c['concept_id'] for c in graph['concepts']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate concept ID.')
    relation_ids, triples = set(), set()
    for r in graph['relations']:
        triple = (r['source'], r['type'], r['target'])
        if r['source'] not in ids or r['target'] not in ids:
            raise ValueError('Relation endpoint is missing.')
        if r['relation_id'] in relation_ids or triple in triples:
            raise ValueError('Duplicate relation ID or triple.')
        relation_ids.add(r['relation_id'])
        triples.add(triple)
    used_chunks = set()
    for item in graph['concepts'] + graph['relations']:
        for e in item['evidence']:
            if not e['quote'] or e['quote'] not in chunks[e['chunk_id']]['text']:
                raise ValueError('Nonliteral evidence in reviewed output.')
            used_chunks.add(e['chunk_id'])
    if used_chunks != set(graph['input_chunk_ids']):
        raise ValueError('Input chunk list does not match evidence.')


def apply_review(root, review):
    if review.get('independent_human_review') is not False:
        raise ValueError('This assisted review must not claim independent human approval.')
    for entry in review['protected_files'] + review['inputs']:
        if digest(inside(root, entry['path'])) != entry['sha256']:
            raise ValueError('Input changed after review: ' + entry['path'])
    chunks = {}
    for filename in ('chunks.jsonl', 'figure_supplements.jsonl'):
        for line in (root / 'corpus/chunks' / filename).read_text(encoding='utf-8').splitlines():
            if line.strip():
                c = json.loads(line)
                chunks[c['chunk_id']] = c
    evidence = {}
    for ref in review['evidence']:
        if ref['ref'] in evidence or ref['start'] < 0 or ref['end'] <= ref['start']:
            raise ValueError('Invalid evidence reference or offsets.')
        if chunks[ref['chunk_id']]['text'][ref['start']:ref['end']] != ref['quote']:
            raise ValueError('Review evidence offsets changed.')
        evidence[ref['ref']] = {'chunk_id': ref['chunk_id'], 'quote': ref['quote']}
    validator = Draft202012Validator(json.loads((root / 'schemas/extraction.schema.json').read_text(encoding='utf-8')))
    results, found, existing = [], set(), set()
    for source in review['inputs']:
        graph = json.loads(inside(root, source['path']).read_text(encoding='utf-8'))
        original_relations = copy.deepcopy(graph['relations'])
        for concept in graph['concepts']:
            cid = concept['concept_id']
            existing.add(cid)
            change = review['concept_updates'].get(cid)
            if not change:
                continue
            found.add(cid)
            concept['description_pt'] = change['description_pt']
            for alias in change.get('add_aliases', []):
                if alias not in concept['aliases']:
                    concept['aliases'].append(alias)
            for ref in change.get('evidence_refs', []):
                if evidence[ref] not in concept['evidence']:
                    concept['evidence'].append(copy.deepcopy(evidence[ref]))
            concept['review_note'] = concept.get('review_note', '') + '\n' + change['note']
        if graph['relations'] != original_relations:
            raise ValueError('Source review must preserve existing relation records.')
        graph['input_chunk_ids'] = sorted({e['chunk_id'] for item in graph['concepts'] + graph['relations'] for e in item['evidence']})
        validate_graph(graph, chunks, validator)
        results.append((source['output'], graph))
    if found != set(review['concept_updates']):
        raise ValueError('A concept update has no corresponding input concept.')
    new_concepts = []
    for definition in review['new_concepts']:
        if definition['concept_id'] in existing:
            raise ValueError('New manual concept conflicts with existing IDs.')
        existing.add(definition['concept_id'])
        concept = {k: copy.deepcopy(v) for k, v in definition.items() if k != 'evidence_refs'}
        concept['evidence'] = [copy.deepcopy(evidence[ref]) for ref in definition['evidence_refs']]
        new_concepts.append(concept)
    manual = {'schema_version': '0.1.0', 'extraction_method': 'manual_reference',
              'input_chunk_ids': sorted({e['chunk_id'] for c in new_concepts for e in c['evidence']}),
              'concepts': new_concepts, 'relations': []}
    validate_graph(manual, chunks, validator)
    results.append((review['manual_output'], manual))
    # Validate every output before writing any file.
    if len({name for name, _ in results}) != len(results):
        raise ValueError('Duplicate output paths.')
    for name, _ in results:
        if inside(root, name).exists():
            raise ValueError('Choose a new output path: ' + name)
    for name, graph in results:
        path = inside(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, required=True)
    args = parser.parse_args()
    results = apply_review(ROOT, json.loads(args.review.read_text(encoding='utf-8')))
    for name, graph in results:
        print(f"{name}: {len(graph['concepts'])} concepts, {len(graph['relations'])} relations; {graph['extraction_method']}")


if __name__ == '__main__':
    main()
