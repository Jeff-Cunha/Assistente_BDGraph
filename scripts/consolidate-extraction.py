"""Consolidate validated per-chunk candidates conservatively, without model/API calls."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def normalize(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def stable_id(prefix, value):
    slug = re.sub('[^a-z0-9]+', '_', normalize(value)).strip('_')[:55] or 'concept'
    digest = hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]
    return f'{prefix}_{slug}_{digest}'


def dedupe_evidence(items):
    by_key = {(e['chunk_id'], e['quote']): e for e in items}
    return [by_key[k] for k in sorted(by_key)]


def validate_candidate(candidate, chunks, schema, registry):
    Draft202012Validator(schema).validate(candidate)
    chunk_id = candidate['chunk_id']
    if chunk_id not in chunks:
        raise ValueError(f'Unknown chunk: {chunk_id}')
    local = [c['local_id'] for c in candidate['concepts']]
    if len(local) != len(set(local)):
        raise ValueError(f'Duplicate local IDs: {chunk_id}')
    for c in candidate['concepts']:
        if c['existing_concept_id'] is not None and c['existing_concept_id'] not in registry:
            raise ValueError('Unknown canonical ID; preserve the registry used by the extraction.')
    for item in candidate['concepts'] + candidate['relations']:
        if item['review_status'] == 'flagged' and not item['review_note'].strip():
            raise ValueError('Flagged item requires a review note.')
        for e in item['evidence']:
            if e['chunk_id'] != chunk_id or not e['quote'].strip() or e['quote'] not in chunks[chunk_id]['text']:
                raise ValueError(f'Nonliteral or cross-chunk evidence: {chunk_id}')
    for r in candidate['relations']:
        if r['source_local_id'] not in local or r['target_local_id'] not in local:
            raise ValueError('Missing local relation endpoint.')


def consolidate(candidates, chunks, registry_list, schema):
    registry = {c['concept_id']: c for c in registry_list}
    if len(registry) != len(registry_list):
        raise ValueError('Duplicate registry IDs.')
    names = {}
    for c in registry_list:
        name = normalize(c['canonical_name'])
        if name in names:
            raise ValueError('Duplicate canonical registry names.')
        names[name] = c['concept_id']
    concepts, relations, mappings, issues = {}, {}, [], []
    seen_chunks = set()
    for candidate in sorted(candidates, key=lambda c: c['chunk_id']):
        validate_candidate(candidate, chunks, schema, registry)
        chunk_id = candidate['chunk_id']
        if chunk_id in seen_chunks:
            raise ValueError(f'Multiple responses for {chunk_id}; choose one run explicitly.')
        seen_chunks.add(chunk_id)
        local_map = {}
        for message in candidate['issues']:
            issues.append({'chunk_id': chunk_id, 'kind': 'model_issue', 'note': message})
        for c in sorted(candidate['concepts'], key=lambda c: c['local_id']):
            name = normalize(c['canonical_name'])
            proposed = c['existing_concept_id']
            seed = registry.get(proposed) if proposed else None
            note = c['review_note'].strip()
            flagged = c['review_status'] == 'flagged'
            if seed:
                labels = [seed['canonical_name'], seed['name_pt']] + seed['aliases']
                if name not in {normalize(label) for label in labels}:
                    raise ValueError(f'Canonical ID/name mismatch: {proposed}; requires manual resolution.')
                cid, reason = proposed, 'explicit_registry_reference'
            elif name in names:
                cid, reason = names[name], 'exact_canonical_name'
                seed = registry.get(cid)
            else:
                cid, reason = stable_id('C', name), 'new_canonical_name'
            expected_category = seed['category'] if seed else concepts.get(cid, c)['category']
            if c['category'] != expected_category:
                raise ValueError(f'Category conflict for {name}; requires manual resolution.')
            canonical_name = seed['canonical_name'] if seed else c['canonical_name'].strip()
            names[normalize(canonical_name)] = cid
            names[name] = cid
            aliases = set(c['aliases']) | {c['canonical_name'], c['name_pt']}
            if seed:
                aliases |= set(seed['aliases']) | {seed['canonical_name'], seed['name_pt']}
            if cid not in concepts:
                concepts[cid] = {
                    'concept_id': cid, 'canonical_name': canonical_name,
                    'name_pt': seed['name_pt'] if seed else c['name_pt'].strip(),
                    'aliases': sorted(aliases), 'category': c['category'],
                    'description_pt': c['description_pt'], 'evidence': [],
                    'review_status': 'pending', 'review_note': '',
                }
            target = concepts[cid]
            # Preserve alternate descriptions for review; don't silently declare them equivalent.
            if target['description_pt'] != c['description_pt']:
                issues.append({'chunk_id': chunk_id, 'kind': 'alternative_description',
                               'concept_id': cid, 'description_pt': c['description_pt']})
            target['aliases'] = sorted(set(target['aliases']) | aliases)
            target['evidence'] = dedupe_evidence(target['evidence'] + c['evidence'])
            if flagged:
                target['review_status'] = 'flagged'
            if note:
                target['review_note'] = '\n'.join(sorted(set(filter(None, [target['review_note'], note]))))
            local_map[c['local_id']] = cid
            mappings.append({'chunk_id': chunk_id, 'local_id': c['local_id'], 'concept_id': cid, 'reason': reason})
        for r in candidate['relations']:
            source, target = local_map[r['source_local_id']], local_map[r['target_local_id']]
            key = (source, r['type'], target)
            if key not in relations:
                relations[key] = {'relation_id': stable_id('R', '|'.join(key)),
                                  'source': source, 'type': r['type'], 'target': target,
                                  'assertion_kind': 'explicit', 'evidence': [],
                                  'review_status': 'pending', 'review_note': ''}
            rel = relations[key]
            rel['evidence'] = dedupe_evidence(rel['evidence'] + r['evidence'])
            if r['review_status'] == 'flagged':
                rel['review_status'] = 'flagged'
            if r['review_note'].strip():
                rel['review_note'] = '\n'.join(sorted(set(filter(None, [rel['review_note'], r['review_note'].strip()]))))
    # Shared aliases are review signals, never sufficient for automatic merging.
    alias_index = {}
    for cid, c in concepts.items():
        for label in [c['canonical_name'], c['name_pt']] + c['aliases']:
            alias_index.setdefault(normalize(label), set()).add(cid)
    for alias, ids in sorted(alias_index.items()):
        if len(ids) > 1:
            issues.append({'kind': 'ambiguous_alias', 'alias': alias, 'concept_ids': sorted(ids)})
            for cid in ids:
                concepts[cid]['review_status'] = 'flagged'
                concepts[cid]['review_note'] += f'\nAlias compartilhado: {alias}; conferir equivalência.'
    for r in relations.values():
        if any(concepts[cid]['review_status'] == 'flagged' for cid in (r['source'], r['target'])):
            r['review_status'] = 'flagged'
            r['review_note'] += '\nUm conceito desta relação exige revisão.'
    result = {'schema_version': '0.1.0', 'extraction_method': 'llm_candidates',
              'input_chunk_ids': sorted(seen_chunks),
              'concepts': sorted(concepts.values(), key=lambda c: c['concept_id']),
              'relations': sorted(relations.values(), key=lambda r: r['relation_id'])}
    return result, {'mappings': mappings, 'issues': issues,
                    'note': 'Structural consolidation only. No automatic semantic approval; all items pending or flagged.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', nargs='+', type=Path, required=True,
                        help='Explicit .candidates.json files from one chosen run per chunk.')
    parser.add_argument('--registry', type=Path, default=ROOT / 'data/extraction/sample.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        parser.error('Output must stay inside this project.')
    if output.exists() and any(output.iterdir()):
        parser.error('Output directory is not empty; use a new one.')
    chunks = {}
    for name in ('chunks.jsonl', 'figure_supplements.jsonl'):
        for line in (ROOT / 'corpus/chunks' / name).read_text(encoding='utf-8-sig').splitlines():
            if line.strip():
                c = json.loads(line)
                if c['chunk_id'] in chunks:
                    raise ValueError('Duplicate corpus chunk ID.')
                chunks[c['chunk_id']] = c
    registry_data = json.loads(args.registry.read_text(encoding='utf-8-sig'))
    schema = json.loads((ROOT / 'schemas/extraction-candidates.schema.json').read_text(encoding='utf-8-sig'))
    candidates = [json.loads(path.read_text(encoding='utf-8-sig')) for path in args.candidates]
    result, review = consolidate(candidates, chunks, registry_data['concepts'], schema)
    final_schema = json.loads((ROOT / 'schemas/extraction.schema.json').read_text(encoding='utf-8-sig'))
    Draft202012Validator(final_schema).validate(result)
    review['source_files'] = [{'path': str(p.resolve()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in args.candidates]
    review['registry_sha256'] = hashlib.sha256(args.registry.read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    for name, data in [('extraction.json', result), ('review.json', review)]:
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Consolidated {len(result['concepts'])} concepts and {len(result['relations'])} relations; manual review required.")


if __name__ == '__main__':
    main()
