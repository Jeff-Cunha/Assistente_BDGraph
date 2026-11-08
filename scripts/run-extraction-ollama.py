"""Run bounded extraction on localhost Ollama, without reading any cloud API key."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('candidate_checks', ROOT / 'scripts/run-extraction-gemini.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


def build_payload(record, model='qwen3:8b', context=16384, output_tokens=8192, json_mode=False):
    return {
        'model': model, 'stream': False, 'think': False, 'keep_alive': '10m',
        'format': 'json' if json_mode else record['response_schema'],
        'messages': [
            {'role': 'system', 'content': record['system_instruction']},
            {'role': 'user', 'content': json.dumps(
                {'input': record['input'], 'response_schema': record['response_schema']} if json_mode else record['input'],
                ensure_ascii=False)},
        ],
        'options': {'temperature': 0, 'seed': 42, 'num_ctx': context,
                    'num_predict': output_tokens},
    }


def parse_response(response):
    if not response.get('done') or response.get('done_reason') != 'stop':
        raise ValueError('Incomplete generation; refusing truncated candidates.')
    return json.loads(response['message']['content'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'data/extraction/pilot-inputs/requests.jsonl')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/extraction/ollama-pilot')
    parser.add_argument('--model', default='qwen3:8b')
    parser.add_argument('--limit', type=int, default=1)
    parser.add_argument('--context', type=int, default=16384)
    parser.add_argument('--output-tokens', type=int, default=8192)
    parser.add_argument('--timeout', type=int, default=240)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--json-mode', action='store_true', help='Use JSON mode instead of constrained-schema decoding; local validation remains mandatory.')
    args = parser.parse_args()
    if min(args.limit, args.context, args.output_tokens, args.timeout) <= 0:
        parser.error('Numeric limits must be positive.')
    if args.output_tokens >= args.context:
        parser.error('Output budget must be smaller than the total context.')
    input_bytes = args.input.read_bytes()
    records = [json.loads(line) for line in input_bytes.decode('utf-8-sig').splitlines() if line.strip()][:args.limit]
    if not records:
        parser.error('Input is empty.')
    for record in records:
        if hashlib.sha256(record['input']['text'].encode('utf-8')).hexdigest() != record['input_text_sha256']:
            parser.error('Input text checksum mismatch.')
        if not record['request_id'].replace('_', '').isalnum():
            parser.error('Invalid request ID.')
        checks.Draft202012Validator.check_schema(record['response_schema'])
    if args.dry_run:
        print(f'Dry run OK: {len(records)} request(s), {args.model}, context={args.context}; no call.')
        return
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        parser.error('Output must remain inside the project.')
    if output.exists() and any(output.iterdir()):
        parser.error('Choose a new output directory; existing runs are preserved.')
    # Bypass HTTP proxy variables for this loopback-only adapter.
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = 'http://127.0.0.1:11434'
    with client.open(base + '/api/version', timeout=10) as r:
        server = json.load(r)
    with client.open(base + '/api/tags', timeout=10) as r:
        models = json.load(r)['models']
    model_info = next((m for m in models if m.get('name') == args.model), None)
    if model_info is None:
        parser.error('Model is not installed locally; pull it first. No automatic download or cloud fallback.')
    if 'cloud' in args.model.casefold() or model_info.get('remote_host'):
        parser.error('Cloud-backed model is not allowed by this local adapter.')
    output.mkdir(parents=True, exist_ok=True)
    manifest = {'provider': 'ollama_local', 'base_url': base, 'server_version': server.get('version'),
                'model': args.model, 'model_digest': model_info.get('digest'),
                'started_at': datetime.now(timezone.utc).isoformat(),
                'input_sha256': hashlib.sha256(input_bytes).hexdigest(),
                'settings': {'num_ctx': args.context, 'num_predict': args.output_tokens,
                             'temperature': 0, 'seed': 42, 'think': False,
                             'output_mode': 'json' if args.json_mode else 'json_schema'}, 'runs': []}
    failed = False
    for record in records:
        rid = record['request_id']
        run = {'request_id': rid, 'status': 'started'}
        try:
            payload = build_payload(record, args.model, args.context, args.output_tokens, args.json_mode)
            request = urllib.request.Request(base + '/api/chat', method='POST',
                                            headers={'Content-Type': 'application/json'},
                                            data=json.dumps(payload).encode('utf-8'))
            start = time.monotonic()
            with client.open(request, timeout=args.timeout) as r:
                response = json.load(r)
            run['duration_seconds'] = round(time.monotonic() - start, 3)
            (output / f'{rid}.raw.json').write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding='utf-8')
            data = parse_response(response)
            checks.validate_candidates(data, record)
            (output / f'{rid}.candidates.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            run.update(status='validated_pending_review', concepts=len(data['concepts']),
                       relations=len(data['relations']), prompt_tokens=response.get('prompt_eval_count'),
                       output_tokens=response.get('eval_count'))
        except urllib.error.HTTPError as exc:
            run.update(status='http_error', http_status=exc.code)
            failed = True
        except Exception as exc:
            run.update(status='failed_validation_or_transport', error_type=type(exc).__name__)
            # Validation messages refer only to public corpus/candidates. Don't log HTTP request headers.
            if isinstance(exc, ValueError):
                run['validation_note'] = str(exc)[:2000]
            failed = True
        manifest['runs'].append(run)
        (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"{rid}: {run['status']}", flush=True)
        if failed:
            break
    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
