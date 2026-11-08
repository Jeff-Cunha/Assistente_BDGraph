"""Package only the reviewed corpus and part-1 handoff inputs; never local secrets."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = {}
    for path in (ROOT / 'corpus').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.pyo'):
            files[path.relative_to(ROOT).as_posix()] = path
    for name in ['data/extraction/sample.json', 'schemas/extraction.schema.json',
                 'scripts/validate-extraction.ps1', 'docs/contrato-extracao.md',
                 'docs/amostra-extracao.md', 'docs/revisao-amostra-parte1.md',
                 'docs/entrega-parte1-para-parte2.md']:
        files[name] = ROOT / name
    sources = json.loads((ROOT / 'corpus/metadata/sources.json').read_text(encoding='utf-8-sig'))
    sample = json.loads(files['data/extraction/sample.json'].read_text(encoding='utf-8-sig'))
    chunks = {}
    for name in ('chunks.jsonl', 'figure_supplements.jsonl'):
        for line in (ROOT / 'corpus/chunks' / name).read_text(encoding='utf-8-sig').splitlines():
            if line.strip():
                c = json.loads(line)
                if c['chunk_id'] in chunks:
                    raise ValueError('Duplicate chunk ID.')
                chunks[c['chunk_id']] = c
    docs = {s['document_id'] for s in sources}
    for c in chunks.values():
        if c['document_id'] not in docs:
            raise ValueError('Unknown document.')
        for parent in c.get('parent_chunk_ids', []):
            if parent not in chunks or chunks[parent]['document_id'] != c['document_id']:
                raise ValueError('Invalid supplement parent.')
    mentions = set()
    for c in sample['concepts']:
        for e in c['evidence']:
            if e['quote'] not in chunks[e['chunk_id']]['text']:
                raise ValueError('Nonliteral concept evidence.')
            mentions.add((e['chunk_id'], c['concept_id']))
    for r in sample['relations']:
        for e in r['evidence']:
            if e['quote'] not in chunks[e['chunk_id']]['text']:
                raise ValueError('Nonliteral relation evidence.')
            mentions.update((e['chunk_id'], cid) for cid in (r['source'], r['target']))
    stats = {'documents': len(docs), 'chunks': len(chunks), 'concepts': len(sample['concepts']),
             'semantic_relationships': len(sample['relations']), 'contains_relationships': len(chunks),
             'supplements_relationships': sum(len(c.get('parent_chunk_ids', [])) for c in chunks.values()),
             'mentions_relationships': len(mentions), 'extraction_method': sample['extraction_method']}
    hashes = {}
    for name, path in sorted(files.items()):
        if path.name.startswith('.env') or path.suffix in ('.exe', '.msi'):
            raise ValueError('Forbidden file in handoff package.')
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    readme = files['docs/entrega-parte1-para-parte2.md'].read_bytes()
    hashes['README.md'] = hashlib.sha256(readme).hexdigest()
    manifest = {'contract_version': '0.1.0', 'purpose': 'reviewed_manual_reference_for_part_2',
                'expected_counts': stats, 'files_sha256': hashes,
                'note': 'Counts specify the recommended full-corpus + manual-sample import, not an executed Neo4j load.'}
    output = ROOT / 'outputs/parte1-para-parte2.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, path in sorted(files.items()):
            z.write(path, name)
        z.writestr('README.md', readme)
        z.writestr('handoff-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:
            raise ValueError('ZIP CRC error.')
        for name, digest in hashes.items():
            if hashlib.sha256(z.read(name)).hexdigest() != digest:
                raise ValueError(f'ZIP hash mismatch: {name}')
    print(json.dumps({'zip': str(output), 'files': len(hashes) + 1, 'expected_counts': stats}, ensure_ascii=False))


if __name__ == '__main__':
    main()
