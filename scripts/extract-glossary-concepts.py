"""Extract source-authored glossary entries, without generating definitions or relations."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def clean(s):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', '', s)).split())


def extract(chunks, known_concepts=None):
    active = {}
    entries = []
    known_names = {}
    for c in known_concepts or []:
        for name in [c['canonical_name'], c['name_pt']] + c['aliases']:
            known_names.setdefault(clean(name).casefold(), set()).add(c['concept_id'])
    for c in sorted(chunks, key=lambda c: (c['document_id'], c['chunk_id'])):
        doc = c['document_id']
        for block in re.finditer(r'[^\n]+(?:\n(?!\n)[^\n]+)*', c['text']):
            text = block.group()
            heading = re.match(r'^(#{1,6})\s+(.+)', text)
            if heading:
                level, title = len(heading[1]), clean(heading[2]).casefold()
                if title.startswith('key terms'):
                    active[doc] = level
                elif doc in active and level <= active[doc]:
                    del active[doc]
                continue
            if doc not in active:
                continue
            markers = []
            for marker in re.finditer(r'<strong>(?P<label>[^<>]+)</strong>\s*', text):
                label = marker['label'].strip()
                body_start = marker.end()
                if label.endswith(':'):
                    label = label[:-1].strip()
                elif text[body_start:].startswith(':'):
                    body_start += 1
                else:
                    continue
                markers.append((marker.start(), body_start, label))
            for pos, (local_start, body_start, label) in enumerate(markers):
                local_end = markers[pos + 1][0] if pos + 1 < len(markers) else len(text)
                local_end = local_start + len(text[local_start:local_end].rstrip())
                quote = text[local_start:local_end]
                tail = text[body_start:local_end].strip()
                if not tail:
                    continue
                surface = clean(label)
                canonical = surface.casefold()
                acronym = re.search(r'\s+\(([A-Z][A-Z0-9]{1,8})\)$', surface)
                aliases = [surface]
                if acronym:
                    canonical = surface[:acronym.start()].casefold()
                    aliases.append(acronym[1])
                ids = set()
                for name in [canonical] + aliases:
                    ids.update(known_names.get(name.casefold(), set()))
                digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]
                entry = {'candidate_id': f"{c['chunk_id']}_G{block.start() + local_start}",
                    'group_id': 'G_' + digest, 'existing_concept_id': next(iter(ids)) if len(ids) == 1 else None,
                    'canonical_name_en': canonical, 'surface': surface, 'aliases': aliases,
                    'definition_source_text': tail, 'document_id': doc, 'chunk_id': c['chunk_id'],
                    'source_url': c['source_url'], 'quote': quote, 'start': block.start() + local_start, 'end': block.start() + local_end,
                    'extraction_method': 'source_glossary_rule', 'review_status': 'pending',
                    'note': 'Source definition preserved, not fact-checked. Portuguese translation and concept granularity require review.'}
                if len(ids) > 1:
                    entry['note'] += ' Ambiguous existing concept IDs: ' + ', '.join(sorted(ids))
                if surface in ('EID', 'SIN'):
                    entry['note'] += ' May be an identifier from an example rather than a general concept.'
                assert c['text'][entry['start']:entry['end']] == entry['quote']
                entries.append(entry)
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or (output.exists() and any(output.iterdir())):
        parser.error('Choose a new output directory inside project.')
    raw = (ROOT / 'corpus/chunks/chunks.jsonl').read_bytes()
    chunks = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    known = json.loads((ROOT / 'data/extraction/sample.json').read_text(encoding='utf-8'))['concepts']
    entries = extract(chunks, known)
    issues = json.loads((ROOT / 'corpus/metadata/figure_source_issues.json').read_text(encoding='utf-8'))
    for e in entries:
        e['source_issue_ids_in_document'] = [i['issue_id'] for i in issues if i['document_id'] == e['document_id']]
        if e['source_issue_ids_in_document']:
            e['note'] += ' Document-level source issues exist; these do not necessarily concern this particular definition.'
        if 'Boyce-Codd' in e['surface']:
            e['note'] += ' BCNF is outside the initial normalization-through-3NF scope; decide whether to include.'
    output.mkdir(parents=True)
    (output / 'concept-definitions.jsonl').write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in entries), encoding='utf-8')
    (output / 'manifest.json').write_text(json.dumps({'method': 'source_glossary_rule',
        'input_sha256': hashlib.sha256(raw).hexdigest(), 'entries': len(entries),
        'groups': len({e['group_id'] for e in entries}),
        'documents': sorted({e['document_id'] for e in entries}),
        'note': 'Candidates only, not accepted graph facts; no semantic relations, translation, or model calls generated.'}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Extracted {len(entries)} source definitions into {output}; review pending.")


if __name__ == '__main__':
    main()
