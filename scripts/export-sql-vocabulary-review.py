"""Export only explicitly reviewed SQL-term occurrences, using the common rule-review gate."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rule_review', ROOT / 'scripts/export-glossary-review.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--occurrences', type=Path, required=True)
    p.add_argument('--review', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not args.output.resolve().is_relative_to(ROOT) or args.output.exists():
        p.error('Choose a new output file inside project.')
    raw = args.occurrences.read_bytes()
    review = json.loads(args.review.read_text(encoding='utf-8'))
    if hashlib.sha256(raw).hexdigest() != review['occurrences_sha256']:
        raise ValueError('Source occurrences changed after review.')
    entries = []
    for line in raw.decode('utf-8').splitlines():
        if line.strip():
            e = json.loads(line)
            e['candidate_id'] = e['chunk_id'] + ':' + e['concept_id']
            entries.append(e)
    chunks = {c['chunk_id']: c for c in (json.loads(line) for line in
        (ROOT / 'corpus/chunks/chunks.jsonl').read_text(encoding='utf-8').splitlines())}
    graph = gate.export(entries, review, chunks)
    schema = json.loads((ROOT / 'schemas/extraction.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(schema).validate(graph)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(graph, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"Exported {len(graph['concepts'])} reviewed SQL vocabulary concepts; no semantic edges added.")


if __name__ == '__main__':
    main()
