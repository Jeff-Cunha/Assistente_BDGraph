"""Package an explicit reviewed release with file hashes, excluding local setup and secrets."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/entrega-parte1-revisao-fontes.zip')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        parser.error('Choose a new ZIP path inside the project.')
    release = json.loads((ROOT / 'data/release/current.json').read_text(encoding='utf-8'))
    for item in release['primary_files']:
        path = (ROOT / item['path']).resolve()
        if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Primary file does not match release hash.')
    files = {}
    for directory in ('corpus', 'data', 'schemas', 'scripts', 'tests', 'docs'):
        for path in (ROOT / directory).rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix in ('.pyc', '.pyo'):
                continue
            if not path.resolve().is_relative_to(ROOT):
                raise ValueError('Symlink leaves the project.')
            if path.name.startswith('.env') or path.suffix.casefold() in ('.exe', '.msi', '.pem', '.key'):
                raise ValueError('Forbidden local setup or credential file.')
            files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name in ('.gitignore', '.gitattributes', 'requirements-extraction.txt'):
        if (ROOT / name).exists():
            files[name] = (ROOT / name).read_bytes()
    files['README.md'] = (ROOT / 'docs/entrega-parte1-atualizada.md').read_bytes()
    manifest = dict(release=release['release'], independent_human_review=False,
        human_review=release.get('human_review'),
        expected_counts={k:release[k] for k in ('documents','chunks','unique_concepts','unique_semantic_triples')},
        files_sha256={name:hashlib.sha256(raw).hexdigest() for name,raw in sorted(files.items())},
        note='Audit ZIP includes historical candidates/raw responses. Import only current.json primary_files. Reading copies are display-only; source evidence remains unchanged.')
    files['delivery-manifest.json'] = (json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            archive.writestr(name, raw)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(files):
            raise ValueError('Archive integrity failure.')
        for name, expected in manifest['files_sha256'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError('Archived file hash mismatch: ' + name)
    print(json.dumps(dict(zip=str(output),files=len(files),bytes=output.stat().st_size,expected_counts=manifest['expected_counts']),ensure_ascii=False))


if __name__ == '__main__':
    main()
