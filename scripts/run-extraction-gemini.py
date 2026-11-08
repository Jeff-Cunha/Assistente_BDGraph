"""Execute a bounded pilot, preserving raw responses and locally validating candidates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def configuration():
    values = {}
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, sep, value = line.partition('=')
            if sep and key.strip() in ('GEMINI_API_KEY', 'GEMINI_MODEL'):
                values[key.strip()] = value.strip().strip('\"\'')
    return {key: os.environ.get(key, values.get(key, default)) for key, default in
            [('GEMINI_API_KEY', ''), ('GEMINI_MODEL', 'gemini-3.8-flash')]}


def validate_candidates(data, record):
    Draft202012Validator(record['response_schema']).validate(data)
    chunk = record['input']
    if data['chunk_id'] != chunk['chunk_id']:
        raise ValueError('Response refers to a different chunk.')
    concepts = data['concepts']
    ids = [c['local_id'] for c in concepts]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate local concept IDs.')
    known = {c['concept_id'] for c in chunk['known_concepts']}
    for concept in concepts:
        if concept['existing_concept_id'] is not None and concept['existing_concept_id'] not in known:
            raise ValueError('Unknown canonical ID proposed by model.')
    for item in concepts + data['relations']:
        if item['review_status'] == 'flagged' and not item['review_note'].strip():
            raise ValueError('Flagged candidate must explain its issue.')
        for e in item['evidence']:
            if e['chunk_id'] != chunk['chunk_id'] or not e['quote'].strip() or e['quote'] not in chunk['text']:
                raise ValueError('Evidence is not a literal quote in the input chunk.')
    triples = set()
    for relation in data['relations']:
        if relation['source_local_id'] not in ids or relation['target_local_id'] not in ids:
            raise ValueError('Relation endpoint does not exist.')
        triple = (relation['source_local_id'], relation['type'], relation['target_local_id'])
        if triple in triples:
            raise ValueError('Duplicate relation.')
        triples.add(triple)


def build_payload(record):
    return {
        'systemInstruction': {'parts': [{'text': record['system_instruction']}]},
        'contents': [{'role': 'user', 'parts': [{'text': json.dumps({
            'input': record['input'], 'response_schema': record['response_schema']}, ensure_ascii=False)}]}],
        'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0, 'maxOutputTokens': 16384},
    }


def response_text(response):
    candidates = response.get('candidates', [])
    if not candidates or candidates[0].get('finishReason') != 'STOP':
        raise ValueError('Generation blocked, incomplete, or missing a STOP finish reason.')
    text = ''.join(p.get('text', '') for p in candidates[0].get('content', {}).get('parts', [])
                   if not p.get('thought'))
    return json.loads(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'data/extraction/pilot-inputs/requests.jsonl')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/extraction/pilot-results')
    parser.add_argument('--limit', type=int, default=1)
    parser.add_argument('--delay', type=float, default=15)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.limit < 1 or args.delay < 0:
        parser.error('Limit must be positive; delay must be non-negative.')
    raw_input = args.input.read_bytes()
    records = [json.loads(line) for line in raw_input.decode('utf-8-sig').splitlines() if line.strip()][:args.limit]
    if not records:
        parser.error('No requests found.')
    for r in records:
        if not re.fullmatch(r'extract_[A-Za-z0-9_]+', r['request_id']):
            parser.error('Invalid request ID.')
        if hashlib.sha256(r['input']['text'].encode('utf-8')).hexdigest() != r['input_text_sha256']:
            parser.error('Input text hash mismatch.')
        Draft202012Validator.check_schema(r['response_schema'])
    settings = configuration()
    model = settings['GEMINI_MODEL']
    if not re.fullmatch(r'[A-Za-z0-9._-]+', model):
        parser.error('Invalid model identifier.')
    if args.dry_run:
        print(f"Dry run OK: {len(records)} request(s), model={model}; no API call.")
        return
    if not settings['GEMINI_API_KEY']:
        parser.error('Configure GEMINI_API_KEY in local .env or environment. Never paste it into chat.')
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        parser.error('Output must remain inside the project.')
    if output.exists() and any(output.iterdir()):
        parser.error('Output already contains a run. Choose a new directory; no implicit retries.')
    output.mkdir(parents=True, exist_ok=True)
    manifest = {'provider': 'gemini', 'model': model, 'started_at': datetime.now(timezone.utc).isoformat(),
                'input_sha256': hashlib.sha256(raw_input).hexdigest(), 'runs': [],
                'note': 'Account billing tier is not verified by this script. No automatic retries.'}
    failed = False
    for index, record in enumerate(records):
        if index:
            time.sleep(args.delay)
        rid = record['request_id']
        run = {'request_id': rid, 'status': 'started'}
        try:
            request = urllib.request.Request(
                f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                data=json.dumps(build_payload(record)).encode('utf-8'), method='POST',
                headers={'Content-Type': 'application/json', 'x-goog-api-key': settings['GEMINI_API_KEY']})
            start = time.monotonic()
            with urllib.request.urlopen(request, timeout=120) as http:
                response = json.load(http)
            run['duration_seconds'] = round(time.monotonic() - start, 3)
            (output / f'{rid}.raw.json').write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding='utf-8')
            candidates = response_text(response)
            validate_candidates(candidates, record)
            (output / f'{rid}.candidates.json').write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding='utf-8')
            run.update(status='validated_pending_review', usage=response.get('usageMetadata', {}))
        except urllib.error.HTTPError as exc:
            run.update(status='http_error', http_status=exc.code)
            # Retain only a bounded, redacted provider message; never headers or full body.
            try:
                error_body = json.loads(exc.read(32768))
                message = str(error_body.get('error', {}).get('message', ''))
                message = message.replace(settings['GEMINI_API_KEY'], '[REDACTED]')
                message = re.sub(r'AIza[A-Za-z0-9_-]+', '[REDACTED]', message)
                run['provider_message'] = message[:2000]
            except Exception:
                pass
            failed = True
        except Exception as exc:
            run.update(status='failed_validation_or_transport', error_type=type(exc).__name__)
            failed = True
        manifest['runs'].append(run)
        (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"{rid}: {run['status']}")
        if failed:
            break
    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
