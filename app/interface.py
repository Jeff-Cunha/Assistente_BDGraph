"""HTTP interface for the Assistente_BDGraph (parte 5).

One question at a time: the local model takes about two minutes, so the request returns a
job identifier and the page polls it. Nothing is answered twice, and a refused answer is
reported as a refusal instead of being smoothed into text.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import mimetypes
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import engine, planner

STATIC = Path(__file__).resolve().parent / 'static'
app = FastAPI(title='Assistente BD Graph', docs_url='/api/docs')
mimetypes.add_type('font/woff2', '.woff2')     # Windows registry has no woff2 entry
app.mount('/static', StaticFiles(directory=STATIC), name='static')
POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix='answer')
JOBS: dict[str, dict] = {}
PREFERRED_MODELS = ('qwen3:8b', 'qwen3:4b')


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=400)
    model: str | None = None
    mode: str = engine.MODE_HYBRID


def default_model():
    names = [item['name'] for item in engine.ollama_status().get('models', [])]
    for name in PREFERRED_MODELS:
        if name in names:
            return name
    return names[0] if names else PREFERRED_MODELS[0]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _work(job_id, question, model, mode):
    job = JOBS[job_id]

    def step(label):
        job['step'] = label
        job['updated_at'] = _now()

    job.update(status='running', started_at=_now(), step='Preparando a consulta')
    try:
        answer = engine.answer_question(question, model=model, mode=mode, on_step=step)
        job['file'] = str(engine.save_run(job_id, answer))
        job.update(status='done', step='Concluído', answer=answer)
    except planner.PlanError as exc:
        job.update(status='unmatched', step='Sem correspondência no grafo',
                   message=str(exc), suggestions=exc.suggestions)
    except engine.grounding.GroundingError as exc:
        job.update(status='rejected', step='Resposta recusada',
                   message=f'A resposta do modelo não passou na verificação: {exc}')
    except engine.EngineError as exc:
        job.update(status='error', step='Falha', message=str(exc))
    except Exception as exc:                       # never hide a failure behind a spinner
        job.update(status='error', step='Falha',
                   message=f'{type(exc).__name__}: {exc}')
    finally:
        job['updated_at'] = _now()


@app.get('/')
def index():
    return FileResponse(STATIC / 'index.html')


@app.get('/api/health')
def health():
    report = engine.health()
    report['model_default'] = default_model()
    report['modes'] = list(engine.MODES)
    return report


@app.get('/api/models')
def models():
    return engine.ollama_status()


@app.get('/api/concepts')
def concepts():
    try:
        with engine.database() as (driver, database_name):
            catalog = engine.concepts(driver, database_name)
    except engine.EngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return {'concepts': catalog}


@app.get('/api/suggest')
def suggest(q: str = ''):
    """Concept names that match what is being typed; the graph is the only vocabulary."""
    if len(q.strip()) < 2:
        return {'suggestions': []}
    try:
        with engine.database() as (driver, database_name):
            catalog = engine.concepts(driver, database_name)
    except engine.EngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    ranked = planner.rank_concepts(q, catalog)
    # While someone types, the concept that explains more of what was typed comes first,
    # so "chave prim" offers "chave primária" before the bare concept "chave".
    ordered = sorted(ranked, key=lambda item: (-item['covered'], -item['terms'], -item['score']))
    return {'suggestions': [{'id': item['id'], 'name_pt': item['name_pt'],
                             'score': item['score']} for item in ordered[:6]]}


@app.post('/api/ask')
def ask(body: Question):
    question = body.question.strip()
    if len(question) < 3:
        raise HTTPException(status_code=422, detail='Pergunta curta demais.')
    if body.mode not in engine.MODES:
        raise HTTPException(status_code=422,
                            detail=f'Modo invalido: use um de {list(engine.MODES)}.')
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {'job_id': job_id, 'question': question,
                    'model': body.model or default_model(), 'mode': body.mode,
                    'status': 'queued',
                    'step': 'Na fila', 'created_at': _now(), 'updated_at': _now()}
    POOL.submit(_work, job_id, question, JOBS[job_id]['model'], body.mode)
    return {'job_id': job_id, 'model': JOBS[job_id]['model']}


@app.get('/api/job/{job_id}')
def job(job_id: str):
    record = JOBS.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Trabalho não encontrado.')
    return record


@app.get('/api/runs')
def runs():
    """Runs kept on disk, newest first; the page can reopen any of them."""
    if not engine.RUNS.exists():
        return {'runs': []}
    found = []
    for folder in engine.RUNS.iterdir():
        answer = folder / 'answer.json'
        if answer.is_file():
            found.append({'job_id': folder.name,
                          'modified': answer.stat().st_mtime})
    found.sort(key=lambda item: item['modified'], reverse=True)
    return {'runs': found[:20]}


@app.get('/api/runs/{job_id}')
def run(job_id: str):
    path = engine.RUNS / job_id / 'answer.json'
    if not path.is_file():
        raise HTTPException(status_code=404, detail='Execução não encontrada.')
    return FileResponse(path, media_type='application/json')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
