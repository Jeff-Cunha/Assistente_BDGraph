"""Prepare auditable per-chunk LLM inputs; makes no network calls."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_chunks(include_figures=False):
    paths = [ROOT / 'corpus/chunks/chunks.jsonl']
    if include_figures:
        paths.append(ROOT / 'corpus/chunks/figure_supplements.jsonl')
    chunks = {}
    for path in paths:
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip():
                continue
            chunk = json.loads(line)
            if chunk['chunk_id'] in chunks:
                raise ValueError(f"Duplicate chunk: {chunk['chunk_id']}")
            if not chunk['text'].strip():
                raise ValueError(f"Empty chunk: {chunk['chunk_id']}")
            chunks[chunk['chunk_id']] = chunk
    return chunks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--documents', nargs='+', default=['D03', 'D07'])
    parser.add_argument('--include-figures', action='store_true',
                        help='Opt in to supplements; unresolved visual details still require review.')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/extraction/pilot-inputs')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        parser.error('Output must stay inside the project directory.')
    if output.exists() and any(output.iterdir()):
        parser.error('Output is not empty. Select a new directory to preserve existing runs.')
    chunks = load_chunks(args.include_figures)
    missing = set(args.documents) - {c['document_id'] for c in chunks.values()}
    if missing:
        parser.error(f'Unknown document IDs: {sorted(missing)}')
    selected = [c for c in chunks.values() if c['document_id'] in args.documents]
    prompt = (ROOT / 'docs/prompt-extracao.md').read_text(encoding='utf-8-sig')
    schema_path = ROOT / 'schemas/extraction-candidates.schema.json'
    schema = json.loads(schema_path.read_text(encoding='utf-8-sig'))
    sample = json.loads((ROOT / 'data/extraction/sample.json').read_text(encoding='utf-8-sig'))
    # Vocabulary only: don't expose reference answers or their supporting quotes.
    registry = [{k: c[k] for k in ('concept_id', 'canonical_name', 'name_pt', 'aliases')}
                for c in sample['concepts']]
    records = []
    for chunk in selected:
        record = {
            'request_id': 'extract_' + chunk['chunk_id'],
            'system_instruction': prompt,
            'response_schema': schema,
            'input': {
                'chunk_id': chunk['chunk_id'],
                'document_id': chunk['document_id'],
                'content_type': chunk.get('content_type', 'page_text'),
                'text': chunk['text'],
                'source_url': chunk['source_url'],
                'known_concepts': registry,
                'figure_ids': chunk.get('figure_ids', []),
                'parent_chunk_ids': chunk.get('parent_chunk_ids', []),
            },
            'input_text_sha256': hashlib.sha256(chunk['text'].encode('utf-8')).hexdigest(),
        }
        records.append(record)
    output.mkdir(parents=True, exist_ok=True)
    payload = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records)
    (output / 'requests.jsonl').write_text(payload, encoding='utf-8', newline='\n')
    manifest = {
        'format_version': '0.1.0', 'stage': 'prepared_not_executed',
        'documents': args.documents, 'include_figures': args.include_figures,
        'request_count': len(records),
        'input_chunk_ids': [r['input']['chunk_id'] for r in records],
        'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
        'schema_sha256': hashlib.sha256(schema_path.read_bytes()).hexdigest(),
        'requests_sha256': hashlib.sha256(payload.encode('utf-8')).hexdigest(),
        'notes': ['Known vocabulary seeded from a manual sample; not an independent evaluation.',
                  'No API call, generated extraction, credentials or cost incurred by this script.'],
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Prepared {len(records)} requests in {output}; no model executed.")


if __name__ == '__main__':
    main()
