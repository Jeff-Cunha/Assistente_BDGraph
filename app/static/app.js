/* Assistente BD Graph — tela de consulta.
   Sem frameworks: um formulário, um polling e um desenho de grafo em SVG. */

const $ = (selector, root = document) => root.querySelector(selector);
const el = (tag, attrs = {}, html = '') => {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else node.setAttribute(key, value);
  }
  if (html) node.innerHTML = html;
  return node;
};

const esc = (text) => String(text ?? '').replace(/[&<>"']/g,
  (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

const LEVELS = { high: 'sustentação alta', medium: 'sustentação média', low: 'sustentação baixa' };

const state = { polling: null, started: 0 };

/* ---------------- boot ---------------- */

async function boot() {
  bind();
  await Promise.all([loadHealth(), loadRuns()]);
}

function bind() {
  $('#ask').addEventListener('submit', (event) => {
    event.preventDefault();
    ask($('#question').value.trim());
  });
  document.querySelectorAll('#examples button').forEach((button) => {
    button.addEventListener('click', () => {
      $('#question').value = button.textContent.trim();
      ask(button.textContent.trim());
    });
  });
  let timer = null;
  $('#question').addEventListener('input', () => {
    clearTimeout(timer);
    const value = $('#question').value.trim();
    if (value.length < 3) { $('#suggest').hidden = true; return; }
    timer = setTimeout(() => loadSuggestions(value), 280);
  });
}

async function loadHealth() {
  const box = $('#status');
  try {
    const health = await (await fetch('/api/health')).json();
    const neo = health.neo4j || {};
    const ollama = health.ollama || {};
    box.innerHTML = '';
    box.append(
      pill(neo.online ? 'ok' : 'bad',
        neo.online
          ? `Neo4j · ${neo.nodes?.Concept ?? 0} conceitos · ${neo.semantic_relations ?? 0} relações`
          : 'Neo4j fora do ar'),
      pill(ollama.online ? 'ok' : 'bad',
        ollama.online ? `Ollama ${ollama.version || ''} · ${(ollama.models || []).length} modelo(s)` : 'Ollama fora do ar'));
    $('#col-neo4j').textContent = neo.online ? (neo.database || 'neo4j') : 'offline';
    $('#col-ollama').textContent = ollama.online ? (ollama.version || 'online') : 'offline';
    $('#col-corpus').textContent = neo.online
      ? `${neo.nodes?.Chunk ?? 0} trechos · ${neo.nodes?.Document ?? 0} documentos` : '—';
    const select = $('#model');
    select.innerHTML = '';
    for (const model of ollama.models || []) {
      const option = el('option', { value: model.name }, esc(model.name));
      if (model.name === health.model_default) option.selected = true;
      select.append(option);
    }
    if (!select.options.length) select.append(el('option', { value: health.model_default }, esc(health.model_default)));
  } catch (error) {
    box.innerHTML = '';
    box.append(pill('bad', 'servidor sem resposta'));
  }
}

function pill(stateName, text) {
  const node = el('span', { class: 'pill', dataset: { state: stateName } }, `<i class="dot"></i>${esc(text)}`);
  return node;
}

async function loadRuns() {
  const list = $('#runs');
  try {
    const data = await (await fetch('/api/runs')).json();
    if (!data.runs.length) return;
    list.innerHTML = '';
    for (const run of data.runs.slice(0, 8)) {
      const when = new Date(run.modified * 1000).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
      const item = el('li');
      const button = el('button', { type: 'button', title: `Abrir execução ${run.job_id}` }, `${esc(when)} · ${esc(run.job_id)}`);
      button.addEventListener('click', () => openRun(run.job_id));
      item.append(button);
      list.append(item);
    }
  } catch (error) { /* the rail keeps its placeholder */ }
}

async function loadSuggestions(text) {
  try {
    const data = await (await fetch(`/api/suggest?q=${encodeURIComponent(text)}`)).json();
    const box = $('#suggest');
    box.innerHTML = '';
    if (!data.suggestions.length) { box.hidden = true; return; }
    for (const item of data.suggestions) {
      const chip = el('button', { type: 'button', title: `Conceito do grafo (${item.id})` }, esc(item.name_pt));
      chip.addEventListener('click', () => { $('#question').value = item.name_pt; box.hidden = true; });
      box.append(chip);
    }
    box.hidden = false;
  } catch (error) { /* suggestions are optional */ }
}

/* ---------------- asking ---------------- */

async function ask(question) {
  if (question.length < 3) return;
  $('#suggest').hidden = true;
  $('#empty').hidden = true;
  $('#ticket').hidden = true;
  $('#progress').hidden = false;
  $('#progress-step').textContent = 'Enviando a pergunta';
  $('#submit').disabled = true;
  state.started = Date.now();
  startTicking();
  try {
    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, model: $('#model').value,
                            mode: $('#mode') ? $('#mode').value : 'hybrid' }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `HTTP ${response.status}`);
    }
    const { job_id: jobId } = await response.json();
    poll(jobId);
  } catch (error) {
    stopTicking();
    $('#progress').hidden = true;
    showFailure('Não foi possível enviar a pergunta', String(error.message || error), []);
    $('#submit').disabled = false;
  }
}

function startTicking() {
  stopTicking();
  state.polling = setInterval(() => {
    $('#progress-time').textContent = `${Math.round((Date.now() - state.started) / 1000)}s`;
  }, 1000);
}

function stopTicking() {
  if (state.polling) clearInterval(state.polling);
  state.polling = null;
}

function poll(jobId) {
  const tick = async () => {
    let job;
    try {
      job = await (await fetch(`/api/job/${jobId}`)).json();
    } catch (error) {
      setTimeout(tick, 2500);
      return;
    }
    if (job.status === 'queued' || job.status === 'running') {
      $('#progress-step').textContent = job.step || 'Consultando';
      setTimeout(tick, 1800);
      return;
    }
    stopTicking();
    $('#progress').hidden = true;
    $('#submit').disabled = false;
    if (job.status === 'done') {
      render(job.answer, jobId);
      loadRuns();
    } else {
      showFailure(
        { unmatched: 'A pergunta não corresponde a nada no grafo',
          rejected: 'A resposta não passou na verificação',
          error: 'A execução falhou' }[job.status] || 'Falha',
        job.message || '', job.suggestions || []);
    }
  };
  setTimeout(tick, 1200);
}

async function openRun(jobId) {
  $('#empty').hidden = true;
  $('#progress').hidden = true;
  try {
    const answer = await (await fetch(`/api/runs/${jobId}`)).json();
    render(answer, jobId);
  } catch (error) {
    showFailure('Não foi possível abrir a execução', jobId, []);
  }
}

/* ---------------- failure ---------------- */

function showFailure(title, message, suggestions) {
  const ticket = $('#ticket');
  ticket.hidden = false;
  ticket.innerHTML = '';
  const notice = el('div', { class: 'notice' });
  notice.append(el('p', {}, `<strong>${esc(title)}</strong>`));
  if (message) notice.append(el('p', {}, esc(message)));
  if (suggestions.length) {
    notice.append(el('p', { class: 'label' }, 'Conceitos parecidos no grafo'));
    const list = el('ul');
    for (const suggestion of suggestions) list.append(el('li', {}, esc(suggestion)));
    notice.append(list);
  }
  ticket.append(notice);
}

/* ---------------- render ---------------- */

function render(answer, jobId = '') {
  const ticket = $('#ticket');
  ticket.hidden = false;
  ticket.innerHTML = '';

  const reading = answer.reading || {};
  const support = answer.support || {};
  const level = support.level || 'low';
  const model = answer.model || {};

  const meta = el('div', { class: 'ticket__meta' });
  meta.append(el('span', { class: 'verdict', dataset: { level } }, esc(LEVELS[level] || level)));
  meta.append(el('div', {}, `${esc(model.model || '')}`));
  meta.append(el('div', {}, `${esc(answer.elapsed_seconds ?? '—')}s · ${esc(jobId || '')}`));

  const head = el('header', { class: 'ticket__head' });
  const questionBox = el('div');
  questionBox.append(el('p', { class: 'label' }, 'Pergunta'));
  questionBox.append(el('h2', { class: 'ticket__question' }, esc(answer.question)));
  if (reading.explanation) {
    questionBox.append(el('p', { class: 'params' }, esc(reading.explanation)));
  }
  head.append(questionBox, meta);

  const left = el('div');
  const answerText = answer.answer_pt || 'Sem resposta: as evidências não sustentaram nenhuma afirmação.';
  left.append(el('p', { class: `answer${answer.answered ? '' : ' answer--refused'}` }, esc(answerText)));

  const citations = new Map((answer.citations || []).map((citation) => [citation.evidence_id, citation]));

  if ((answer.claims || []).length) {
    left.append(el('h3', { class: 'label' }, 'Afirmações e evidências'));
    const list = el('ol', { class: 'claims' });
    for (const claim of answer.claims) {
      const item = el('li', { dataset: { unsupported: 'false' } });
      item.append(document.createTextNode(claim.text || ''));
      for (const id of claim.evidence_ids || []) {
        const citation = citations.get(id);
        item.append(el('span', { class: 'ev', title: citation ? citation.title || '' : id }, esc(id)));
      }
      list.append(item);
    }
    left.append(list);
  }

  if ((answer.dropped_claims || []).length) {
    left.append(el('h3', { class: 'label' }, 'Descartadas por falta de evidência'));
    const list = el('ol', { class: 'claims' });
    for (const claim of answer.dropped_claims) {
      list.append(el('li', { dataset: { unsupported: 'true' } }, esc(claim.text || '')));
    }
    left.append(list);
  }

  const supportBox = el('div', { class: 'support' });
  const reasons = (support.reasons || []).map((reason) => `<li>${esc(reason)}</li>`).join('');
  supportBox.innerHTML = `
    <p><strong>${esc(LEVELS[level] || level)}</strong> · cobertura ${esc(Math.round((support.coverage ?? 0) * 100))}% ·
    ${esc(support.claims_with_evidence ?? 0)} afirmação(ões) com evidência ·
    ${esc(support.distinct_chunks ?? 0)} trecho(s) de ${esc(support.distinct_documents ?? 0)} documento(s) ·
    ${esc(support.unverified_quotes ?? 0)} citação(ões) não verificada(s)</p>
    ${reasons ? `<ul>${reasons}</ul>` : ''}`;
  if ((answer.limitations || []).length) {
    supportBox.append(el('p', { class: 'params' }, esc(answer.limitations.join(' '))));
  }
  left.append(supportBox);

  const right = el('div');

  if (answer.graph && (answer.graph.paths || []).length) {
    const pane = el('section', { class: 'pane' });
    pane.append(el('h3', { class: 'label' }, 'Subgrafo percorrido'));
    pane.append(graphPlate(answer.graph));
    right.append(pane);
  }

  const sources = answer.sources || [];
  if (sources.length) {
    const pane = el('section', { class: 'pane' });
    pane.append(el('h3', { class: 'label' }, 'Fontes'));
    const list = el('ul', { class: 'sources' });
    for (const source of sources) {
      const item = el('li');
      const link = source.source_url
        ? el('a', { href: source.source_url, target: '_blank', rel: 'noopener noreferrer' }, esc(source.title || source.document_id))
        : el('span', {}, esc(source.title || source.document_id));
      item.append(link);
      item.append(el('span', { class: 'path' },
        `${esc(source.document_id)} · ${esc((source.chunk_ids || []).join(', '))}`));
      list.append(item);
    }
    pane.append(list);

    if ((answer.citations || []).length) {
      pane.append(el('h3', { class: 'label' }, 'Citações verificadas'));
      const quotes = el('ul', { class: 'quotes' });
      for (const citation of answer.citations) {
        const item = el('li');
        item.append(el('span', {}, `${esc(citation.quote || '')}`));
        item.append(el('span', { class: 'src' },
          `${esc(citation.evidence_id)} · ${esc(citation.title || citation.document_id)} · ${esc(citation.chunk_id)}`));
        quotes.append(item);
      }
      pane.append(quotes);
    }
    right.append(pane);
  }

  if (answer.graph && !answer.graph.cypher) {
    const pane = el('section', { class: 'pane' });
    pane.append(el('h3', { class: 'label' }, 'Recuperação'));
    const graph = answer.graph;
    const line = el('p', { class: 'params' },
      `modo: ${esc(answer.mode || graph.mode || 'híbrido')} · canais: ${esc((graph.channels || []).join(' + ') || '—')}`
      + (graph.graph_algorithm ? ` · grafo: ${esc(graph.graph_algorithm)}` : '')
      + (graph.origins ? ` · origens: ${esc(graph.origins.join(', '))}` : ''));
    pane.append(line);
    pane.append(el('p', { class: 'params' },
      'Este modo não usa plano Cypher: as evidências vêm da busca vetorial e da travessia do grafo.'));
    right.append(pane);
  }

  if (answer.graph && answer.graph.cypher) {
    const pane = el('section', { class: 'pane' });
    const details = el('details');
    details.append(el('summary', {}, 'Consulta Cypher executada'));
    const pre = el('pre', { class: 'cypher' });
    pre.innerHTML = highlightCypher(answer.graph.cypher);
    details.append(pre);
    const params = Object.entries(answer.graph.parameters || {})
      .map(([key, value]) => `$${key} = ${JSON.stringify(value)}`).join('   ·   ');
    details.append(el('p', { class: 'params' }, esc(params)));
    const plan = answer.plan ? `plano: ${answer.plan.start.label} ${answer.plan.start.id} · ${answer.plan.hops.length} salto(s) · limite ${answer.plan.limit}` : '';
    if (plan) details.append(el('p', { class: 'params' }, esc(plan)));
    pane.append(details);
    right.append(pane);
  }

  const body = el('div', { class: 'ticket__body' });
  body.append(left, right);
  ticket.append(head, body);
}

function highlightCypher(text) {
  return esc(text)
    .replace(/\b(MATCH|RETURN|WHERE|LIMIT|WITH|ORDER BY|AS)\b/g, '<b>$1</b>')
    .replace(/(\$[a-z0-9_]+)/gi, '<b>$1</b>');
}

/* ---------------- graph plate ---------------- */

function graphPlate(graph) {
  const nodes = new Map();
  const edges = [];
  for (const path of graph.paths || []) {
    const pathNodes = path.nodes || [];
    for (const node of pathNodes) {
      if (!node || !node.id) continue;
      if (!nodes.has(node.id)) {
        nodes.set(node.id, { id: node.id, label: node.label, name: node.name_pt || node.name || node.id });
      }
    }
    // A structural plan (concept -> chunk) brings only the relationship types, no evidence.
    const relationships = path.relationships
      || (path.relationship_types || []).map((type) => ({ type }));
    pathNodes.forEach((node, index) => {
      const next = pathNodes[index + 1];
      const relationship = relationships[index];
      if (!next || !relationship) return;
      edges.push({
        source: node.id,
        target: next.id,
        type: relationship.type,
        quotes: parseQuotes(relationship.evidence_quotes_json),
        review: relationship.review_status,
      });
    });
  }

  const wrapper = el('div', { class: 'plate' });
  const tip = el('div', { class: 'plate__tip', dataset: { show: 'false' } });
  wrapper.append(tip);

  const width = 660;
  const height = Math.max(210, Math.min(460, 130 + nodes.size * 22));
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', `Subgrafo com ${nodes.size} nós e ${edges.length} relações`);

  const layout = pathLayout([...nodes.values()], edges, width, height);

  const edgeLayer = document.createElementNS(svgNS, 'g');
  const nodeLayer = document.createElementNS(svgNS, 'g');
  svg.append(edgeLayer, nodeLayer);

  const edgeElements = [];
  for (const edge of edges) {
    const from = layout.get(edge.source);
    const to = layout.get(edge.target);
    if (!from || !to) continue;
    const group = document.createElementNS(svgNS, 'g');
    group.setAttribute('class', 'edge');
    const line = document.createElementNS(svgNS, 'line');
    line.setAttribute('x1', from.x); line.setAttribute('y1', from.y);
    line.setAttribute('x2', to.x); line.setAttribute('y2', to.y);
    group.append(line);
    const label = document.createElementNS(svgNS, 'text');
    const midX = (from.x + to.x) / 2;
    const midY = (from.y + to.y) / 2;
    const angle = Math.atan2(to.y - from.y, to.x - from.x);
    label.setAttribute('x', midX - Math.sin(angle) * 9);
    label.setAttribute('y', midY + Math.cos(angle) * 9);
    label.setAttribute('text-anchor', 'middle');
    label.textContent = edge.type || '';
    group.append(label);
    group.addEventListener('mouseenter', () => showTip(tip, wrapper, label, edge));
    group.addEventListener('mouseleave', () => { tip.dataset.show = 'false'; });
    edgeLayer.append(group);
    edgeElements.push({ group, edge });
  }

  const nodeElements = [];
  for (const node of nodes.values()) {
    const point = layout.get(node.id);
    const group = document.createElementNS(svgNS, 'g');
    group.setAttribute('class', 'node');
    group.setAttribute('data-label', node.label);
    const radius = node.label === 'Concept' ? 7 : 4.5;
    const circle = document.createElementNS(svgNS, 'circle');
    circle.setAttribute('cx', point.x); circle.setAttribute('cy', point.y); circle.setAttribute('r', radius);
    group.append(circle);
    const text = document.createElementNS(svgNS, 'text');
    const anchorRight = point.x > width * 0.62;
    text.setAttribute('x', point.x + (anchorRight ? -10 : 10));
    text.setAttribute('y', point.y + 3);
    text.setAttribute('text-anchor', anchorRight ? 'end' : 'start');
    text.textContent = node.name;
    group.append(text);
    group.addEventListener('mouseenter', () => {
      const neighbourEdges = edgeElements.filter(({ edge }) => edge.source === node.id || edge.target === node.id);
      edgeElements.forEach(({ group: edgeGroup, edge }) => edgeGroup.classList.toggle('hot',
        neighbourEdges.some((candidate) => candidate.edge === edge)));
      nodeElements.forEach(({ group: nodeGroup, item }) => nodeGroup.classList.toggle('hot',
        item.id === node.id || neighbourEdges.some(({ edge }) => edge.source === item.id || edge.target === item.id)));
      tip.dataset.show = 'true';
      tip.innerHTML = `<strong>${esc(node.name)}</strong><br>${esc(node.label)} · ${esc(node.id)}`;
      placeTip(tip, wrapper, point, width);
    });
    group.addEventListener('mouseleave', () => {
      edgeElements.forEach(({ group: edgeGroup }) => edgeGroup.classList.remove('hot'));
      nodeElements.forEach(({ group: nodeGroup }) => nodeGroup.classList.remove('hot'));
      tip.dataset.show = 'false';
    });
    nodeLayer.append(group);
    nodeElements.push({ group, item: node });
  }

  wrapper.append(svg);
  const legend = el('div', { class: 'plate__legend' });
  const counts = {};
  for (const node of nodes.values()) counts[node.label] = (counts[node.label] || 0) + 1;
  for (const [label, total] of Object.entries(counts)) {
    legend.append(el('span', {}, `<i data-label="${esc(label)}"></i>${esc(label)} · ${total}`));
  }
  legend.append(el('span', {}, `${edges.length} relação(ões)`));
  wrapper.append(legend);
  return wrapper;
}

function parseQuotes(raw) {
  try {
    const parsed = JSON.parse(raw || '[]');
    return Array.isArray(parsed) ? parsed.filter((item) => item && item.quote) : [];
  } catch (error) {
    return [];
  }
}

function showTip(tip, wrapper, label, edge) {
  const first = edge.quotes[0];
  tip.dataset.show = 'true';
  tip.innerHTML = first
    ? `<strong>${esc(edge.type)}</strong> · ${esc(edge.review || '')}<br>“${esc(first.quote.slice(0, 220))}”<br><em>${esc(first.chunk_id || '')}</em>`
    : `<strong>${esc(edge.type)}</strong> · ${esc(edge.review || 'sem evidência literal')}`;
  const box = wrapper.getBoundingClientRect();
  const point = label.getBoundingClientRect();
  tip.style.left = `${Math.min(Math.max(point.left - box.left - 40, 8), box.width - 260)}px`;
  tip.style.top = `${point.top - box.top + 18}px`;
}

function placeTip(tip, wrapper, point, width) {
  tip.style.left = `${Math.min(Math.max(point.x - 60, 8), width - 240)}px`;
  tip.style.top = `${point.y + 16}px`;
}

/* Layout by distance along the path: the graph in an answer is a chain of
   relationships, so placing each node by its hop index reads better than a force cloud.
   Deterministic: the same answer always draws the same plate. */
function pathLayout(nodes, edges, width, height) {
  const rank = new Map();
  for (const node of nodes) rank.set(node.id, 0);
  for (let round = 0; round < nodes.length; round += 1) {
    let moved = false;
    for (const edge of edges) {
      if (!rank.has(edge.source) || !rank.has(edge.target)) continue;
      const next = rank.get(edge.source) + 1;
      if (rank.get(edge.target) < next && next < nodes.length) {
        rank.set(edge.target, next);
        moved = true;
      }
    }
    if (!moved) break;
  }

  const columns = new Map();
  for (const node of nodes) {
    const column = rank.get(node.id);
    if (!columns.has(column)) columns.set(column, []);
    columns.get(column).push(node);
  }

  const order = [...columns.keys()].sort((a, b) => a - b);
  const span = Math.max(order.length - 1, 1);
  const padX = 96;
  const padY = 34;
  const positions = new Map();
  const columnWidth = (width - padX * 2) / span;
  order.forEach((column, columnIndex) => {
    const members = columns.get(column);
    const x = padX + columnIndex * columnWidth;
    const usable = height - padY * 2;
    const gap = members.length > 1 ? Math.min(78, usable / (members.length - 1)) : 0;
    const top = height / 2 - (gap * (members.length - 1)) / 2;
    members.forEach((node, index) => {
      const wave = columnIndex % 2 === 0 ? -1 : 1;
      const y = top + index * gap + (members.length === 1 ? wave * 16 : 0);
      positions.set(node.id, { x, y: Math.min(Math.max(y, padY), height - padY) });
    });
  });
  return positions;
}

boot();
