"""Corre o conjunto de avaliação nos três modos de recuperação e mede o resultado.

Uso:
  python scripts/run-avaliacao.py --out work/avaliacao/rodada1
  python scripts/run-avaliacao.py --out work/avaliacao/rodada1 --modes vector,hybrid
  python scripts/run-avaliacao.py --dry-run          # valida o encanamento, sem chamar o modelo

Cada resposta é gravada em `<out>/<pergunta>-<modo>/answer.json` e a rodada produz um CSV e um
resumo em Markdown. O gabarito vem das evidências das relações do grafo, nunca das respostas.

Definição de acerto, aplicada igualmente aos três modos:
- pergunta que tem resposta: `answered` verdadeiro, ao menos um documento esperado entre as
  fontes citadas e nenhuma citação não verificada;
- pergunta sem resposta no corpus: `answered` falso (abstenção).
Nível de sustentação e cobertura são reportados à parte, porque medem outra coisa.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import engine                                  # noqa: E402

QUESTIONS = ROOT / 'data' / 'avaliacao' / 'perguntas.jsonl'
MODES = ('vector', 'hybrid', 'graph')
TOP_K = 5
LEVELS = ('high', 'medium', 'low', 'insufficient')


def load_questions(path):
    questions = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            questions.append(json.loads(line))
    return questions


def _quote(text, question):
    module = engine._load('retrieval_parte3', 'retrieval.py')
    return module.find_best_quote(text, question)


def vector_bundle(question, top_k=TOP_K):
    """Baseline: só a busca vetorial, sem nenhuma travessia de grafo."""
    module = engine._load('retrieval_parte3', 'retrieval.py')
    retriever = engine.retriever()
    vector = retriever.embedder.encode([question])[0]
    results = module.vector_search(vector, retriever.precomputed_embeddings, top_k=top_k)
    evidence = []
    for chunk_id, score in results:
        record = retriever.chunks.get(chunk_id)
        text = retriever.texts.get(chunk_id)
        if record is None or not text:
            continue
        meta = retriever.sources.get(record['document_id'], {})
        evidence.append({
            'chunk_id': chunk_id,
            'document_id': record['document_id'],
            'title': meta.get('title', record['document_id']),
            'source_url': record.get('source_url') or meta.get('source_url', ''),
            'section_path': module.format_section_path(
                record, meta.get('title', record['document_id'])),
            'quote': _quote(text, question),
            'review_status': 'accepted',
            'origin': 'vector',
            'relation': None,
            'score': round(float(score), 4),
        })
    return {'question': question, 'language': 'pt-BR',
            'retrieval': {'strategy': 'vector', 'channels': ['vector'],
                          'graph_executed': False, 'max_hops': 0},
            'concepts': [], 'evidence': evidence}


def run_one(question, mode, model, timeout, top_k=TOP_K, max_hops=engine.MAX_EVIDENCE_HOPS):
    if mode == 'vector':
        bundle = vector_bundle(question['pergunta'], top_k)
        return engine.answer_from_evidence(question['pergunta'], bundle, model=model,
                                           mode='vector', timeout=timeout)
    return engine.answer_question(question['pergunta'], model=model, mode=mode,
                                  top_k=top_k, max_hops=max_hops, timeout=timeout)


_NoPlan = ()
try:                                                     # falta de plano é resposta legítima
    from app.planner import PlanError as _PlanError
    _NoPlan = (_PlanError,)
except Exception:                                        # pragma: no cover
    pass


def _abstention_row(question, mode, seconds, reason):
    """Graph mode refusing an off-graph question is an abstention, not a crash."""
    answer = {'answered': False, 'claims': [], 'citations': [],
              'support': {'level': 'insufficient', 'coverage': 0.0, 'unverified_quotes': 0}}
    row = measure(question, answer, mode, seconds)
    row['observacao'] = (row['observacao'] + ' | ' if row['observacao'] else '') +         f'nenhum conceito no grafo: {reason[:120]}'
    return row


def measure(question, answer, mode, seconds):
    """Mechanical marking, identical for every mode; the expected documents come from the graph."""
    answered = bool(answer.get('answered'))
    cited_documents = sorted({citation.get('document_id') for citation in answer.get('citations') or []
                              if citation.get('document_id')})
    expected = [document for document in question.get('documentos') or []]
    expected_hit = bool(set(expected) & set(cited_documents))
    unverified = (answer.get('support') or {}).get('unverified_quotes', 0)
    if question.get('espera_resposta', True):
        correct = answered and expected_hit and unverified == 0
        observation = '' if correct else (
            'não respondeu' if not answered else
            f'documento esperado ausente (citou {", ".join(cited_documents) or "nada"})'
            if not expected_hit else f'{unverified} citação(ões) não verificada(s)')
    else:
        correct = not answered
        observation = '' if correct else 'respondeu a pergunta que não está no corpus'
    support = answer.get('support') or {}
    return {
        'id': question['id'], 'tipo': question['tipo'], 'modo': mode,
        'estado': 'respondida' if answered else 'abstenção',
        'nivel': support.get('level') or '—',
        'cobertura': support.get('coverage'),
        'afirmacoes': len(answer.get('claims') or []),
        'citacoes': len(answer.get('citations') or []),
        'documentos_citados': ','.join(cited_documents),
        'documento_esperado_citado': 'sim' if expected_hit else 'não',
        'nao_verificadas': unverified,
        'segundos': seconds,
        'correta': 'sim' if correct else 'não',
        'observacao': observation,
    }


def summarise(rows):
    lines, table = [], []
    for mode in MODES:
        subset = [row for row in rows if row['modo'] == mode]
        if not subset:
            continue
        total = len(subset)
        correct = sum(1 for row in subset if row['correta'] == 'sim')
        abstentions = [row for row in subset if row['tipo'] == 'sem-resposta']
        answers = [row for row in subset if row['tipo'] != 'sem-resposta']
        levels = {level: sum(1 for row in subset if row['nivel'] == level) for level in LEVELS}
        unverified = sum(row['nao_verificadas'] for row in subset)
        times = [row['segundos'] for row in subset if row['segundos']]
        table.append({
            'modo': mode, 'perguntas': total, 'corretas': correct,
            'acerto': f'{correct / total:.0%}' if total else '—',
            'respondidas': sum(1 for row in subset if row['estado'] == 'respondida'),
            'abstencao_correta': f"{sum(1 for row in abstentions if row['correta'] == 'sim')}/{len(abstentions)}",
            'doc_esperado': f"{sum(1 for row in answers if row['documento_esperado_citado'] == 'sim')}/{len(answers)}",
            'nivel_alto': levels['high'], 'nivel_medio': levels['medium'],
            'nivel_baixo': levels['low'], 'insuficiente': levels['insufficient'],
            'nao_verificadas': unverified,
            'tempo_medio': f'{sum(times) / len(times):.0f} s' if times else '—',
        })
    return table


def write_outputs(out, rows, table, started):
    out.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with (out / 'resultados.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    header = ('| Modo | Perguntas | Corretas | Acerto | Respondidas | Abstenção correta | Doc. esperado '
              '| Alto | Médio | Baixo | Insuf. | Não verificadas | Tempo médio |')
    rule = '|' + '---|' * 13
    body = [f"| {row['modo']} | {row['perguntas']} | {row['corretas']} | {row['acerto']} | "
            f"{row['respondidas']} | {row['abstencao_correta']} | {row['doc_esperado']} | "
            f"{row['nivel_alto']} | {row['nivel_medio']} | {row['nivel_baixo']} | "
            f"{row['insuficiente']} | {row['nao_verificadas']} | {row['tempo_medio']} |"
            for row in table]
    per_question = ['| Pergunta | Tipo | ' + ' | '.join(f'{mode}: acerto / nível' for mode in MODES) + ' |',
                    '|---|---|' + '---|' * len(MODES)]
    ids = sorted({row['id'] for row in rows})
    by_key = {(row['id'], row['modo']): row for row in rows}
    for identifier in ids:
        question = next(row for row in rows if row['id'] == identifier)
        cells = []
        for mode in MODES:
            row = by_key.get((identifier, mode))
            cells.append('—' if row is None else f"{row['correta']} / {row['nivel']}")
        per_question.append(f"| {identifier} | {question['tipo']} | " + ' | '.join(cells) + ' |')

    text = [f"# Avaliação — {started.strftime('%d/%m/%Y %H:%M')}", '',
            'Acerto: pergunta com resposta exige `answered`, documento esperado citado e nenhuma '
            'citação não verificada; pergunta sem resposta exige abstenção. O gabarito de '
            'documentos vem das evidências das relações do grafo.', '',
            *(['## Por modo', '', header, rule, *body, ''] if table else []),
            '## Por pergunta', '', *per_question, '']
    (out / 'resumo.md').write_text('\n'.join(text), encoding='utf-8')
    return out / 'resumo.md'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'work' / 'avaliacao' / 'rodada')
    parser.add_argument('--questions', type=Path, default=QUESTIONS)
    parser.add_argument('--modes', default=','.join(MODES))
    parser.add_argument('--model', default='qwen3:8b')
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--only', help='Identificadores separados por vírgula, para uma rodada curta.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Monta as evidências e mede o gabarito, sem chamar o modelo.')
    args = parser.parse_args()

    modes = [mode.strip() for mode in args.modes.split(',') if mode.strip()]
    unknown = [mode for mode in modes if mode not in MODES]
    if unknown:
        parser.error(f'Modo desconhecido: {unknown}. Use {list(MODES)}.')
    questions = load_questions(args.questions)
    if args.only:
        wanted = {item.strip().upper() for item in args.only.split(',')}
        questions = [question for question in questions if question['id'].upper() in wanted]
    if not questions:
        parser.error('Nenhuma pergunta selecionada.')

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    rows, failures = [], 0
    for question in questions:
        for mode in modes:
            target = out / f"{question['id']}-{mode}"
            answer_path = target / 'answer.json'
            if answer_path.is_file():                      # retoma uma rodada interrompida
                answer = json.loads(answer_path.read_text(encoding='utf-8'))
                seconds = answer.get('elapsed_seconds') or 0
                print(f'{question["id"]} {mode}: reaproveitado', flush=True)
            elif args.dry_run:
                if mode == 'vector':
                    bundle = vector_bundle(question['pergunta'])
                else:
                    bundle = (engine.hybrid_bundle(question['pergunta'], max_hops=engine.MAX_EVIDENCE_HOPS)
                              if mode == 'hybrid' else None)
                documents = sorted({item.get('document_id') for item in (bundle or {}).get('evidence') or []})
                print(f'{question["id"]} {mode}: dry-run | evidências='
                      f'{len((bundle or {}).get("evidence") or [])} | documentos={documents} | '
                      f'esperado={question["documentos"]}', flush=True)
                continue
            else:
                start = time.monotonic()
                try:
                    answer = run_one(question, mode, args.model, args.timeout)
                except _NoPlan as exc:                      # o modo grafo recusou a pergunta
                    seconds = round(time.monotonic() - start, 1)
                    rows.append(_abstention_row(question, mode, seconds, str(exc)))
                    write_outputs(out, rows, summarise(rows), started)
                    continue
                except Exception as exc:                   # uma falha não derruba a rodada
                    failures += 1
                    seconds = round(time.monotonic() - start, 1)
                    print(f'{question["id"]} {mode}: FALHOU {type(exc).__name__}: {exc}', flush=True)
                    # A refusal by the verifier is a result, not a gap in the table.
                    rows.append({
                        'id': question['id'], 'tipo': question['tipo'], 'modo': mode,
                        'estado': 'falha', 'nivel': '—', 'cobertura': None, 'afirmacoes': 0,
                        'citacoes': 0, 'documentos_citados': '',
                        'documento_esperado_citado': 'não', 'nao_verificadas': 0,
                        'segundos': seconds, 'correta': 'não',
                        'observacao': f'{type(exc).__name__}: {str(exc)[:160]}',
                    })
                    write_outputs(out, rows, summarise(rows), started)
                    continue
                seconds = round(time.monotonic() - start, 1)
                target.mkdir(parents=True, exist_ok=True)
                (target / 'answer.json').write_text(
                    json.dumps(answer, ensure_ascii=False, indent=2), encoding='utf-8')
                print(f'{question["id"]} {mode}: {answer.get("answered")} '
                      f'{(answer.get("support") or {}).get("level")} {seconds}s', flush=True)
            rows.append(measure(question, answer, mode, seconds))
            write_outputs(out, rows, summarise(rows), started)

    if args.dry_run:
        return 0
    table = summarise(rows)
    summary = write_outputs(out, rows, table, started)
    print(f'\n{len(rows)} execuções, {failures} falha(s). Resumo em {summary}')
    for row in table:
        print(f"  {row['modo']}: {row['corretas']}/{row['perguntas']} corretas ({row['acerto']}), "
              f"doc esperado {row['doc_esperado']}, não verificadas {row['nao_verificadas']}, "
              f"{row['tempo_medio']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
