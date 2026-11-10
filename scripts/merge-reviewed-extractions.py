"""Union approved outputs of the same extraction method, preserving evidence and IDs."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def merge(graphs):
    methods = {g['extraction_method'] for g in graphs}
    if len(methods) != 1:
        raise ValueError('Do not silently mix manual-reference and model-derived outputs.')
    concepts, names, relations, relation_ids = {}, {}, {}, {}
    for graph in graphs:
        for c in graph['concepts']:
            if c['review_status'] != 'accepted':
                raise ValueError('Only reviewed concepts may enter this union.')
            cid, name = c['concept_id'], c['canonical_name'].strip().casefold()
            if name in names and names[name] != cid:
                raise ValueError('Same canonical name has different IDs; resolve manually.')
            names[name] = cid
            if cid not in concepts:
                concepts[cid] = copy.deepcopy(c)
            else:
                old = concepts[cid]
                if (old['canonical_name'].casefold(), old['category']) != (name, c['category']):
                    raise ValueError('Concept identity conflict.')
                old['aliases'] = sorted(set(old['aliases'] + c['aliases']))
                for e in c['evidence']:
                    if e not in old['evidence']:
                        old['evidence'].append(copy.deepcopy(e))
                old['review_note'] = '\n'.join(dict.fromkeys([old.get('review_note', ''), c.get('review_note', '')]))
        for r in graph['relations']:
            if r['review_status'] != 'accepted':
                raise ValueError('Only reviewed relations may enter this union.')
            key = (r['source'], r['type'], r['target'])
            rid = r['relation_id']
            if rid in relation_ids and relation_ids[rid] != key:
                raise ValueError('Relation ID refers to different triples.')
            relation_ids[rid] = key
            if key not in relations:
                relations[key] = copy.deepcopy(r)
            elif relations[key]['relation_id'] != rid:
                raise ValueError('Same triple has different IDs; resolve before merging.')
            else:
                for e in r['evidence']:
                    if e not in relations[key]['evidence']:
                        relations[key]['evidence'].append(copy.deepcopy(e))
                old_note = relations[key].get('review_note', '')
                relations[key]['review_note'] = '\n'.join(dict.fromkeys([old_note, r.get('review_note', '')]))
    version = '0.1.2' if any(g.get('schema_version', '0.1.0') == '0.1.2' for g in graphs) else '0.1.1' if 'rule_candidates' in methods else '0.1.0'
    return dict(schema_version=version, extraction_method=next(iter(methods)),
        input_chunk_ids=sorted({cid for g in graphs for cid in g['input_chunk_ids']}),
        concepts=sorted(concepts.values(), key=lambda c: c['concept_id']),
        relations=sorted(relations.values(), key=lambda r: r['relation_id']))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs', nargs='+', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        p.error('Choose a new file inside project.')
    schema = json.loads((ROOT / 'schemas/extraction.schema.json').read_text(encoding='utf-8'))
    validator = Draft202012Validator(schema)
    graphs = [json.loads(path.read_text(encoding='utf-8')) for path in args.inputs]
    for g in graphs:
        validator.validate(g)
    result = merge(graphs)
    validator.validate(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    manifest = {'inputs': [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in args.inputs],
                'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                'note': 'Only previously reviewed model-derived outputs combined; manual sample not copied. First description retained when a concept appears twice; original descriptions remain in source files.'}
    output.with_suffix('.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Merged {len(result['concepts'])} concepts and {len(result['relations'])} relations.")


if __name__ == '__main__':
    main()
