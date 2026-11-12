"""Turn a free question into a validated query plan.

The model never writes Cypher here. The plan is built from the graph itself: the
question is matched against the 93 concept names already in Neo4j, and the hops are a
path that actually exists. So every plan the interface runs is one the guard accepts and
the graph can answer, and the same question always produces the same query.
"""
from __future__ import annotations

from collections import Counter
import re
import unicodedata

from . import engine

STOPWORDS = {
    'a', 'o', 'as', 'os', 'de', 'do', 'da', 'dos', 'das', 'e', 'em', 'no', 'na', 'nos',
    'nas', 'um', 'uma', 'uns', 'umas', 'para', 'por', 'com', 'que', 'qual', 'quais',
    'como', 'quando', 'onde', 'entre', 'sobre', 'ao', 'aos', 'se', 'sua', 'seu', 'suas',
    'seus', 'eu', 'me', 'explique', 'explica', 'diferenca', 'relacao', 'relacoes',
    'relaciona', 'ligam', 'liga', 'ligado', 'ligada', 'acontece', 'funciona', 'serve',
    'the', 'of', 'and', 'is', 'are', 'what', 'which', 'how', 'does', 'do', 'in', 'on',
    'to', 'for', 'with', 'between', 'relation', 'relations', 'difference',
}
MIN_SCORE = 0.5
PREFIX = 3


class PlanError(RuntimeError):
    """The question could not be tied to a concept in the graph."""

    def __init__(self, message, suggestions=None):
        super().__init__(message)
        self.suggestions = suggestions or []


def strip_accents(text):
    decomposed = unicodedata.normalize('NFD', text or '')
    return ''.join(char for char in decomposed if unicodedata.category(char) != 'Mn')


def _words(text):
    return re.findall(r'[a-z0-9_]+', strip_accents(text or '').lower())


def _stem(word):
    """Plural noise only; anything stronger would merge concepts the graph keeps apart."""
    if len(word) > 4 and word.endswith('oes'):
        return word[:-3] + 'ao'
    if len(word) > 3 and word.endswith('s'):
        return word[:-1]
    return word


def _tokens(text):
    return {_stem(word) for word in _words(text) if word not in STOPWORDS and len(word) > 2}


def _match(question_token, concept_token):
    if question_token == concept_token:
        return True
    short, long = sorted((question_token, concept_token), key=len)
    return len(short) >= PREFIX and long.startswith(short)


def _stems(text):
    return [_stem(word) for word in _words(text) if word not in STOPWORDS and len(word) > 2]


def rank_concepts(question, catalog):
    """Score every concept by how much of its name the question carries.

    A name that appears as a phrase beats a name that only shares words, and the longer
    name wins a tie: "chave primária" is a better reading of "chave primária" than the
    bare concept "chave", and a single generic word never outranks a specific phrase."""
    question_stems = _stems(question)
    flat = f' {" ".join(question_stems)} '
    ranked = []
    for concept in catalog:
        names = [concept.get('name_pt') or '', concept.get('canonical_name') or '']
        best = None
        for position, name in enumerate(names):
            stems = _stems(name)
            if not stems:
                continue
            hits = sum(1 for stem in stems
                       if any(_match(token, stem) for token in question_stems))
            covered = sum(1 for token in question_stems
                          if any(_match(token, stem) for stem in stems))
            phrase = f' {" ".join(stems)} ' in flat
            score = hits / len(stems) + (0.75 if phrase else 0.0)
            score += 0.05 * (1 - position)          # the Portuguese name is the default
            candidate = (round(score, 2), len(stems), covered)
            if best is None or candidate > best:
                best = candidate
        if best is None or best[0] < MIN_SCORE:
            continue
        ranked.append({'score': best[0], 'terms': max(best[1], 1), 'covered': best[2],
                       'id': concept['id'], 'name_pt': concept.get('name_pt'),
                       'canonical_name': concept.get('canonical_name')})
    ranked.sort(key=lambda item: (-item['score'], -item['terms'], item['id']))
    return ranked


def _edges(path_row):
    """Per-edge type and direction, so a plan can replay a mixed-direction path."""
    nodes = path_row['ids']
    edges = []
    for index, edge in enumerate(path_row['edges']):
        forward = nodes[index] == edge['start']
        edges.append({'type': edge['type'], 'direction': 'out' if forward else 'in'})
    return edges


_PATH = '''
MATCH (a:Concept {{concept_id: $start}}), (b:Concept {{concept_id: $target}})
MATCH p = shortestPath((a)-[*1..{hops}]-(b))
WHERE all(n IN nodes(p) WHERE n:Concept)
RETURN [n IN nodes(p) | n.concept_id] AS ids,
       [i IN range(0, size(relationships(p)) - 1) | {{type: type(relationships(p)[i]),
        start: startNode(relationships(p)[i]).concept_id}}] AS edges
LIMIT 1
'''

_WALK = '''
MATCH p = (:Concept {{concept_id: $start}})-[*{hops}]-(:Concept)
WHERE all(n IN nodes(p) WHERE n:Concept)
RETURN [n IN nodes(p) | n.concept_id] AS ids,
       [i IN range(0, size(relationships(p)) - 1) | {{type: type(relationships(p)[i]),
        start: startNode(relationships(p)[i]).concept_id}}] AS edges
LIMIT 200
'''


def _plan_from_path(start_id, path_row, limit):
    hops = [{'direction': edge['direction'],
             'types': [edge['type']],
             'target_label': 'Concept'} for edge in _edges(path_row)]
    return {'start': {'label': 'Concept', 'id': start_id}, 'hops': hops,
            'include_evidence': True, 'limit': limit}


def _best_walk(driver, database_name, start_id, limit, max_hops):
    """The deepest walk that exists most often: a path the graph can always answer."""
    for depth in range(min(max_hops, engine.MAX_EVIDENCE_HOPS), 0, -1):
        rows = engine.read(driver, database_name, _WALK.format(hops=depth), {'start': start_id})
        if not rows:
            continue
        ranked = Counter()
        first = {}
        for row in rows:
            edges = _edges(row)
            key = tuple((edge['direction'], edge['type']) for edge in edges)
            ranked[key] += 1
            first.setdefault(key, row)
        key, _ = max(ranked.items(), key=lambda item: (item[1], -len(item[0])))
        return _plan_from_path(start_id, first[key], limit), depth, ranked[key]
    return None, 0, 0


STRUCTURAL_FALLBACK = {'start': {'label': 'Concept', 'id': None},
                       'hops': [{'direction': 'in', 'types': ['MENTIONS'],
                                 'target_label': 'Chunk'}],
                       'include_evidence': False, 'limit': 6}


def text_plan(concept_id, max_hops=engine.MAX_EVIDENCE_HOPS):
    """Structural plan used when the concept has no semantic relation to walk.

    It reads the chunks that mention the concept; the quotes come from the stored text of
    those chunks, so the citation is literal even though no edge carries evidence."""
    plan = {'start': {'label': 'Concept', 'id': concept_id},
            'hops': [dict(hop) for hop in STRUCTURAL_FALLBACK['hops']],
            'include_evidence': STRUCTURAL_FALLBACK['include_evidence'],
            'limit': STRUCTURAL_FALLBACK['limit']}
    return engine.guard.validate_plan(plan, max_hops=max_hops)


def build_plan(driver, database_name, question, max_hops=engine.MAX_EVIDENCE_HOPS, limit=12):
    """Return (plan, reading) where reading explains the choice to the person asking."""
    catalog = engine.concepts(driver, database_name)
    ranked = rank_concepts(question, catalog)
    if not ranked:
        # Nothing matched by name: the fulltext index over names and aliases (concept_names)
        # supplies the suggestions. The question is still refused, never answered from here.
        try:
            names = [row['name_pt'] for row
                     in engine.search_concepts(driver, database_name, question, limit=6)
                     if row.get('name_pt')]
        except Exception:      # a suggestion must never turn into a failure of the question
            names = []
        raise PlanError(
            'Nenhum conceito do grafo aparece nessa pergunta. Use um dos termos do grafo, '
            'como "integridade referencial", "chave estrangeira" ou "junção".',
            suggestions=names or [c['name_pt'] for c in catalog[:6]])

    primary = ranked[0]
    reading = {'matched': ranked[:4], 'strategy': 'single-concept',
               'explanation': f'Pergunta ligada ao conceito "{primary["name_pt"]}".'}

    if len(ranked) > 1:
        best = None
        for candidate in ranked[1:4]:
            rows = engine.read(driver, database_name,
                               _PATH.format(hops=min(max_hops, engine.MAX_EVIDENCE_HOPS)),
                               {'start': primary['id'], 'target': candidate['id']})
            if not rows:
                continue
            plan = _plan_from_path(primary['id'], rows[0], limit)
            if best is None or len(plan['hops']) > len(best[0]['hops']):
                best = (plan, candidate)
        if best and len(best[0]['hops']) >= 2:
            plan, target = best
            reading.update(strategy='shortest-path',
                           explanation=(f'Caminho de {len(plan["hops"])} salto(s) entre '
                                        f'"{primary["name_pt"]}" e "{target["name_pt"]}".'),
                           target={'id': target['id'], 'name_pt': target['name_pt']})
            return engine.guard.validate_plan(plan, max_hops=max_hops), reading

    plan, depth, count = _best_walk(driver, database_name, primary['id'], limit, max_hops)
    if plan is not None:
        reading.update(strategy='walk',
                       explanation=(f'Partindo de "{primary["name_pt"]}", o caminho de '
                                    f'{depth} salto(s) mais frequente no grafo '
                                    f'({count} ocorrência(s)).'))
        return engine.guard.validate_plan(plan, max_hops=max_hops), reading

    reading.update(strategy='text',
                   explanation=(f'"{primary["name_pt"]}" ainda não tem relação semântica no '
                                'grafo, então a resposta vem dos trechos que mencionam o '
                                'conceito.'))
    return text_plan(primary['id'], max_hops), reading
