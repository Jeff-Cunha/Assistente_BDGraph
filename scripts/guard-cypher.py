"""Reject unsafe Cypher and compile constrained query plans; no model text becomes syntax.

The knowledge graph is read-only here: a query must use only the labels, relationship
types and properties fixed by the extraction contract, must carry a row limit and must
stay inside the hop budget. Free-form Cypher is the fallback; the preferred path is
compile_plan(), where a model supplies identifiers, relationship types, a direction and
a limit, and every one of them is checked against a fixed list before it reaches Cypher.
"""
import argparse
import json
from pathlib import Path
import re

# Hop budget: one number for the plan, the free-Cypher check, the executor and the
# adapters. Kept small because every extra hop multiplies the paths the database returns.
DEFAULT_MAX_HOPS = 4

ALLOWED_LABELS = frozenset({'Concept', 'Chunk', 'Document'})

ALLOWED_PROPERTIES = {
    'Concept': frozenset({
        'concept_id', 'canonical_name', 'name_pt', 'aliases', 'category',
        'description_pt', 'review_status', 'review_note', 'assertion_kind',
        'evidence_chunk_ids', 'evidence_quotes_json', 'extraction_methods',
        'provenance_json',
    }),
    'Chunk': frozenset({
        'chunk_id', 'document_id', 'text', 'content_type', 'language',
        'section_path', 'source_url', 'word_count', 'chunk_index', 'figure_ids',
        'parent_chunk_ids', 'transcription_status', 'uncertainties',
        'source_issue_ids', 'supplement_id',
    }),
    'Document': frozenset({
        'document_id', 'title', 'source_url', 'language', 'version',
        'collected_at', 'authors', 'license_name', 'license_url',
        'attributions_and_notices', 'quality_status',
    }),
}
# Whitelist of what a generated query may read, not of everything the graph stores:
# Chunk.embedding and the *_json blobs that duplicate other properties stay out on purpose.
RELATIONSHIP_PROPERTIES = frozenset({
    'relation_id', 'relation_ids', 'assertion_kind', 'review_status', 'review_note',
    'extraction_methods', 'evidence_chunk_ids', 'evidence_quotes_json', 'provenance_json',
})
ALL_PROPERTIES = frozenset().union(*ALLOWED_PROPERTIES.values()) | RELATIONSHIP_PROPERTIES

STRUCTURAL_RELATION_TYPES = frozenset({'CONTAINS', 'SUPPLEMENTS', 'MENTIONS'})
SEMANTIC_RELATION_TYPES = frozenset({
    'IS_A', 'SUPPORTS', 'REQUIRES', 'GOVERNS', 'TYPICALLY_USED_IN', 'COMBINES',
    'HAS_FORM', 'PRESERVES', 'RETRIEVES', 'FILTERS', 'GROUPS', 'AGGREGATES',
    'EVALUATED_BEFORE', 'REMOVES_DUPLICATES',
})
ALLOWED_RELATION_TYPES = STRUCTURAL_RELATION_TYPES | SEMANTIC_RELATION_TYPES

ID_PROPERTY = {'Document': 'document_id', 'Chunk': 'chunk_id', 'Concept': 'concept_id'}
NODE_ID_PATTERNS = {
    'Document': re.compile(r'D[0-9]{2}'),
    'Chunk': re.compile(r'D[0-9]{2}_(?:C[0-9]{3}|F[0-9]{3}_S[0-9]{3})'),
    'Concept': re.compile(r'C_[a-z0-9]+(?:_[a-z0-9]+)*'),
}

# Identifiers are compared case-insensitively, so these names cannot be used as aliases.
FORBIDDEN_KEYWORDS = frozenset({
    'CREATE', 'MERGE', 'DELETE', 'DETACH', 'SET', 'REMOVE', 'DROP', 'FOREACH',
    'CALL', 'YIELD', 'LOAD', 'CSV', 'USING', 'PERIODIC', 'COMMIT', 'ROLLBACK',
    'GRANT', 'REVOKE', 'ALTER', 'SHOW', 'TERMINATE', 'INDEX', 'CONSTRAINT',
    'ANALYZE', 'PROFILE', 'EXPLAIN', 'START', 'UNION', 'EXISTS', 'CASE',
    'APOC', 'GDS', 'DBMS',
})

_SCAN = re.compile(r"""
    (?P<whitespace>\s+)
  | (?P<comment>//[^\n]*|/\*.*?\*/)
  | (?P<string>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")
  | (?P<backtick>`[^`]*`)
  | (?P<parameter>\$[A-Za-z_][A-Za-z0-9_]*)
  | (?P<number>[0-9]+(?:\.[0-9]+)?)
  | (?P<word>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<operator><=|>=|<>|->|<-|\.\.|[()\[\]{},:.;|*+\-/=<>])
""", re.VERBOSE | re.DOTALL)


class UnsafeCypher(ValueError):
    """Raised when a query is rejected; the message names the violated rule."""


class InvalidPlan(ValueError):
    """Raised when a query plan does not match the restricted plan format."""


def _fail(message):
    raise UnsafeCypher(message)


def _scan(text):
    """Split a query into typed tokens; unknown characters abort the scan."""
    tokens = []
    position = 0
    while position < len(text):
        match = _SCAN.match(text, position)
        if match is None:
            raise UnsafeCypher(f'Unsupported character at offset {position}: {text[position]!r}')
        position = match.end()
        kind = match.lastgroup
        if kind != 'whitespace':
            tokens.append((kind, match.group()))
    return tokens


def _depths(tokens):
    """Bracket and brace depth recorded before each token, so '[' and '{' report the outer depth."""
    bracket_depth, brace_depth = [], []
    brackets = braces = 0
    for kind, value in tokens:
        bracket_depth.append(brackets)
        brace_depth.append(braces)
        if kind == 'operator':
            if value == '[':
                brackets += 1
            elif value == ']':
                brackets = max(0, brackets - 1)
            elif value == '{':
                braces += 1
            elif value == '}':
                braces = max(0, braces - 1)
    return bracket_depth, brace_depth


def _read_name_list(tokens, start):
    """Read `A|B|C` identifiers starting at `start`."""
    names = []
    index = start
    while index < len(tokens):
        kind, value = tokens[index]
        if kind != 'word':
            return names
        names.append(value)
        index += 1
        if index < len(tokens) and tokens[index] == ('operator', '|'):
            index += 1
            continue
        return names
    return names


def _check_tokens(tokens):
    """Reject constructs that have no place in a read-only analytical query."""
    for kind, value in tokens:
        if kind == 'operator' and value == ';':
            _fail('Only one statement is allowed; a semicolon terminates the query.')
        if kind == 'comment':
            _fail('Comments are not allowed.')
    words = [value.upper() for kind, value in tokens if kind == 'word']
    for word in words:
        if word in FORBIDDEN_KEYWORDS:
            _fail(f'Forbidden clause, keyword or procedure call: {word}.')
    for kind, _ in tokens:
        if kind == 'backtick':
            _fail('Quoted identifiers are not allowed; use the contract names.')
        if kind == 'string':
            _fail('String literals are not allowed; pass values as $parameters.')
    if 'RETURN' not in words:
        _fail('Query must contain a RETURN clause.')
    if 'MATCH' not in words:
        _fail('Query must contain a MATCH clause.')


def _check_names(tokens):
    """Validate node labels, relationship types and property access against the contract."""
    bracket_depth, brace_depth = _depths(tokens)
    labels, relationship_types, properties = set(), set(), set()
    index = 0
    while index < len(tokens):
        kind, value = tokens[index]
        if kind == 'operator' and value == '.':
            target = tokens[index + 1] if index + 1 < len(tokens) else ('', '')
            if target[0] != 'word':
                _fail('Property access must be followed by a property name.')
            if target[1] not in ALL_PROPERTIES:
                _fail(f'Unknown property: {target[1]}.')
            properties.add(target[1])
            index += 2
            continue
        if kind == 'operator' and value == ':':
            if brace_depth[index]:
                # Projection or property-map key: an output field name, not schema.
                index += 1
                continue
            names = _read_name_list(tokens, index + 1)
            if not names:
                _fail('Label or relationship type must be a plain identifier.')
            if bracket_depth[index]:
                for name in names:
                    if name not in ALLOWED_RELATION_TYPES:
                        _fail(f'Unknown relationship type: {name}.')
                relationship_types.update(names)
            else:
                for name in names:
                    if name not in ALLOWED_LABELS:
                        _fail(f'Unknown label: {name}.')
                labels.update(names)
            index += 2 * len(names)
            continue
        index += 1
    return labels, relationship_types, properties


def _matching(tokens, start, opening, closing):
    """Index just past the bracket closing the one at `start`."""
    depth = 0
    for index in range(start, len(tokens)):
        if tokens[index] == ('operator', opening):
            depth += 1
        elif tokens[index] == ('operator', closing):
            depth -= 1
            if depth == 0:
                return index + 1
    _fail(f'Unclosed {opening} in query.')


def _relationship_brackets(tokens):
    """Indices of '[' that start a relationship pattern, identified by the preceding '-'.
    List comprehensions in a RETURN projection are preceded by a keyword or separator."""
    indices = []
    for index, (kind, value) in enumerate(tokens):
        if kind == 'operator' and value == '[' and index:
            previous = tokens[index - 1]
            if previous in {('operator', '-'), ('operator', '<-')}:
                indices.append(index)
    return indices


def _check_variable_length(tokens, start, end, max_hops):
    """A star inside a relationship pattern must have an explicit, small upper bound."""
    inner = tokens[start:end]
    stars = [index for index, token in enumerate(inner) if token == ('operator', '*')]
    if not stars:
        return
    if len(stars) > 1:
        _fail('Only one variable-length marker is allowed per relationship pattern.')
    position = start + stars[0] + 1
    bound = None
    if position < len(tokens) and tokens[position][0] == 'number':
        bound = int(float(tokens[position][1]))
        position += 1
    if position < len(tokens) and tokens[position] == ('operator', '..'):
        position += 1
        if position < len(tokens) and tokens[position][0] == 'number':
            bound = int(float(tokens[position][1]))
        else:
            bound = None
    if bound is None:
        _fail('Variable-length relationship needs an explicit upper bound.')
    if bound > max_hops:
        _fail(f'Variable-length relationship exceeds the hop budget of {max_hops}.')


def _check_relationship_patterns(tokens, max_hops):
    """Every relationship pattern must declare a contract type, a bounded length and fit
    inside the hop budget."""
    brackets = _relationship_brackets(tokens)
    for index in range(len(tokens) - 1):
        if tokens[index] == ('operator', '-') and tokens[index + 1] == ('operator', '-'):
            _fail('Relationship pattern must declare an allowed type.')
    for start in brackets:
        end = _matching(tokens, start, '[', ']')
        if not any(token == ('operator', ':') for token in tokens[start:end]):
            _fail('Relationship pattern must declare an allowed type.')
        _check_variable_length(tokens, start, end, max_hops)
    if len(brackets) > max_hops:
        _fail(f'Query crosses {len(brackets)} relationship patterns; the budget is {max_hops}.')
    return len(brackets)


def _check_unlabeled_nodes(tokens):
    """`MATCH (n)` without a label would scan every label stored in the database.

    A pattern that only reuses a variable already bound with a label is a reference, not a scan."""
    labelled = {tokens[index + 1][1] for index in range(len(tokens) - 2)
                if tokens[index] == ('operator', '(') and tokens[index + 1][0] == 'word'
                and tokens[index + 2] == ('operator', ':')}
    neighbours = {('operator', ','), ('operator', '-'), ('operator', '->'), ('operator', '<-')}
    keywords = {'MATCH', 'OPTIONAL', 'WHERE', 'AND', 'OR'}
    for index in range(1, len(tokens) - 2):
        if tokens[index] != ('operator', '(') or tokens[index + 2] != ('operator', ')'):
            continue
        if tokens[index + 1][0] != 'word' or tokens[index + 1][1] in labelled:
            continue
        previous = tokens[index - 1]
        named = previous[0] == 'word' and previous[1].upper() in keywords
        if named or previous in neighbours:
            _fail(f'Node pattern ({tokens[index + 1][1]}) needs a label: '
                  f'use one of {sorted(ALLOWED_LABELS)}.')


def _return_items(tokens):
    """Split the last RETURN projection on top-level commas, ignoring ORDER BY/SKIP/LIMIT."""
    positions = [index for index, (kind, value) in enumerate(tokens)
                 if kind == 'word' and value.upper() == 'RETURN']
    if not positions:
        return []
    items, current, depth = [], [], 0
    for index in range(positions[-1] + 1, len(tokens)):
        kind, value = tokens[index]
        if kind == 'operator' and value in ('(', '[', '{'):
            depth += 1
        elif kind == 'operator' and value in (')', ']', '}'):
            depth = max(0, depth - 1)
        elif depth == 0 and kind == 'word' and value.upper() in ('ORDER', 'SKIP', 'LIMIT'):
            break
        elif depth == 0 and kind == 'operator' and value == ',':
            items.append(current)
            current = []
            continue
        current.append(tokens[index])
    items.append(current)
    return [item for item in items if item]


def _check_return_projection(tokens):
    """A returned node would expose every stored property, vectors included; a path is allowed."""
    paths = {tokens[index][1] for index in range(len(tokens) - 2)
             if tokens[index][0] == 'word' and tokens[index + 1] == ('operator', '=')
             and tokens[index + 2] == ('operator', '(')}
    for item in _return_items(tokens):
        projection = list(item)
        if projection and projection[0][0] == 'word' and projection[0][1].upper() == 'DISTINCT':
            projection = projection[1:]
        if len(projection) >= 2 and projection[-2][0] == 'word' \
                and projection[-2][1].upper() == 'AS':
            projection = projection[:-2]
        if len(projection) == 1 and projection[0] == ('operator', '*'):
            _fail('RETURN * exposes every property; list the properties instead.')
        if len(projection) == 1 and projection[0][0] == 'word' \
                and projection[0][1] not in paths:
            _fail(f'Returning {projection[0][1]} would expose every property; '
                  'list the properties or aggregate instead.')


def _check_parameters(tokens, parameters):
    required = sorted({value[1:] for kind, value in tokens if kind == 'parameter'})
    if parameters is None:
        return required, []
    missing = sorted(set(required) - set(parameters))
    if missing:
        _fail(f'Missing parameter(s): {", ".join(missing)}.')
    return required, sorted(set(parameters) - set(required))


def _check_limit(tokens, parameters, default_limit, max_limit):
    """Return (limit, injected); a query without LIMIT receives one bound to $limit."""
    position = None
    for index, (kind, value) in enumerate(tokens):
        if kind == 'word' and value.upper() == 'LIMIT':
            position = index
    if position is None:
        return default_limit, True
    target = tokens[position + 1] if position + 1 < len(tokens) else ('', '')
    if target[0] == 'parameter':
        name = target[1][1:]
        if parameters is not None and name in parameters:
            value = parameters[name]
            valid = isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= max_limit
            if not valid:
                _fail(f'${name} must be an integer between 1 and {max_limit}.')
            return value, False
        return None, False
    if target[0] == 'number':
        value = int(float(target[1]))
        if not 1 <= value <= max_limit:
            _fail(f'LIMIT must be between 1 and {max_limit}.')
        return value, False
    _fail('LIMIT must be an integer or a $parameter.')


def validate_cypher(query, parameters=None, max_hops=DEFAULT_MAX_HOPS, max_limit=200,
                    default_limit=25):
    """Validate free-form read-only Cypher and return the checked query with its parameters."""
    if not isinstance(query, str) or not query.strip():
        _fail('Query must be a non-empty string.')
    tokens = _scan(query)
    _check_tokens(tokens)
    _check_unlabeled_nodes(tokens)
    labels, relationship_types, properties = _check_names(tokens)
    relationship_patterns = _check_relationship_patterns(tokens, max_hops)
    required, unused = _check_parameters(tokens, parameters)
    limit, injected = _check_limit(tokens, parameters, default_limit, max_limit)
    _check_return_projection(tokens)
    checked = query.strip()
    final_parameters = dict(parameters or {})
    if injected:
        if 'limit' in final_parameters:
            value = final_parameters['limit']
            valid = isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= max_limit
            if not valid:
                _fail(f'$limit must be an integer between 1 and {max_limit}.')
            limit = value
        else:
            final_parameters['limit'] = default_limit
            limit = default_limit
        checked = f'{checked}\nLIMIT $limit'
        required = sorted(set(required) | {'limit'})
        unused = [name for name in unused if name != 'limit']
    return {
        'query': checked,
        'parameters': final_parameters,
        'labels': sorted(labels),
        'relationship_types': sorted(relationship_types),
        'properties': sorted(properties),
        'relationship_patterns': relationship_patterns,
        'limit': limit,
        'limit_injected': injected,
        'required_parameters': required,
        'unused_parameters': unused,
    }


PLAN_KEYS = frozenset({'start', 'hops', 'include_evidence', 'limit'})
HOP_KEYS = frozenset({'direction', 'types', 'target_label'})
START_KEYS = frozenset({'label', 'id'})
DIRECTIONS = frozenset({'out', 'in', 'both'})


def _require_keys(mapping, keys, required, what):
    if not isinstance(mapping, dict):
        raise InvalidPlan(f'{what} must be an object.')
    unknown = sorted(set(mapping) - keys)
    if unknown:
        raise InvalidPlan(f'Unknown field(s) in {what}: {unknown}.')
    missing = sorted(required - set(mapping))
    if missing:
        raise InvalidPlan(f'Missing field(s) in {what}: {missing}.')


def validate_plan(plan, max_hops=DEFAULT_MAX_HOPS, max_limit=200, default_limit=25):
    """Check the restricted plan format a model is allowed to produce."""
    _require_keys(plan, PLAN_KEYS, {'start', 'hops'}, 'plan')
    _require_keys(plan['start'], START_KEYS, {'label', 'id'}, 'plan.start')
    label = plan['start']['label']
    if label not in ALLOWED_LABELS:
        raise InvalidPlan(f'Unknown label in plan.start: {label}.')
    identifier = plan['start']['id']
    if not isinstance(identifier, str) or not NODE_ID_PATTERNS[label].fullmatch(identifier):
        raise InvalidPlan(f'Invalid {ID_PROPERTY[label]} for label {label}.')
    hops = plan['hops']
    if not isinstance(hops, list) or not 1 <= len(hops) <= max_hops:
        raise InvalidPlan(f'Plan needs between 1 and {max_hops} hops.')
    for position, hop in enumerate(hops, 1):
        name = f'plan.hops[{position}]'
        _require_keys(hop, HOP_KEYS, {'direction', 'types', 'target_label'}, name)
        if hop['direction'] not in DIRECTIONS:
            raise InvalidPlan(f'Unknown direction in hop {position}: {hop["direction"]}.')
        types = hop['types']
        if not isinstance(types, list) or not 1 <= len(types) <= 3:
            raise InvalidPlan(f'Hop {position} needs between 1 and 3 relationship types.')
        if len(set(types)) != len(types):
            raise InvalidPlan(f'Hop {position} repeats a relationship type.')
        for relation in types:
            if relation not in ALLOWED_RELATION_TYPES:
                raise InvalidPlan(f'Unknown relationship type in hop {position}: {relation}.')
        if hop['target_label'] not in ALLOWED_LABELS:
            raise InvalidPlan(f'Unknown target label in hop {position}: {hop["target_label"]}.')
    limit = plan.get('limit', default_limit)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= max_limit:
        raise InvalidPlan(f'Plan limit must be an integer between 1 and {max_limit}.')
    include_evidence = plan.get('include_evidence', True)
    if not isinstance(include_evidence, bool):
        raise InvalidPlan('include_evidence must be a boolean.')
    return {
        'start': {'label': label, 'id': identifier},
        'hops': [{'direction': hop['direction'], 'types': list(hop['types']),
                  'target_label': hop['target_label']} for hop in hops],
        'include_evidence': include_evidence,
        'limit': limit,
    }


def _project(side, with_evidence):
    """RETURN projection for one side of the path; only contract properties are read."""
    if side == 'nodes':
        return ('[x IN nodes(p) | {label: head(labels(x)), '
                'id: coalesce(x.concept_id, x.chunk_id, x.document_id), '
                'name: coalesce(x.name_pt, x.canonical_name, x.title, x.content_type), '
                'name_pt: x.name_pt, canonical_name: x.canonical_name}] AS nodes')
    if with_evidence:
        return ('[x IN relationships(p) | {type: type(x), relation_id: x.relation_id, '
                'source: startNode(x).concept_id, target: endNode(x).concept_id, '
                'review_status: x.review_status, assertion_kind: x.assertion_kind, '
                'evidence_chunk_ids: x.evidence_chunk_ids, '
                'evidence_quotes_json: x.evidence_quotes_json}] AS relationships')
    return '[x IN relationships(p) | type(x)] AS relationship_types'


def compile_plan(plan, max_hops=DEFAULT_MAX_HOPS, default_limit=25, max_limit=200):
    """Compile a validated plan into one deterministic, parameterised path query.
    Only identifiers already checked against fixed lists reach the query text, so the
    result is reproducible, loggable and independent of how the model phrased anything."""
    plan = validate_plan(plan, max_hops, max_limit, default_limit)
    label = plan['start']['label']
    parameters = {'id_0': plan['start']['id'], 'limit': plan['limit']}
    anchor = f'MATCH (n0:{label} {{{ID_PROPERTY[label]}: $id_0}})'
    pattern = f'(n0:{label} {{{ID_PROPERTY[label]}: $id_0}})'
    for index, hop in enumerate(plan['hops'], 1):
        relationship = f'[r{index}:{"|".join(hop["types"])}]'
        node = f'(n{index}:{hop["target_label"]})'
        if hop['direction'] == 'out':
            pattern += f'-{relationship}->{node}'
        elif hop['direction'] == 'in':
            pattern += f'<-{relationship}-{node}'
        else:
            pattern += f'-{relationship}-{node}'
    projection = ', '.join([_project('nodes', plan['include_evidence']),
                            _project('relationships', plan['include_evidence'])])
    query = f'{anchor}\nMATCH p={pattern}\nRETURN {projection}\nLIMIT $limit'
    checked = validate_cypher(query, parameters, max_hops=max(max_hops, len(plan['hops'])))
    return {
        'plan': plan,
        'cypher': query,
        'parameters': parameters,
        'labels': checked['labels'],
        'relationship_types': checked['relationship_types'],
        'hops': len(plan['hops']),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--plan', type=Path, help='JSON query plan to compile.')
    source.add_argument('--cypher', type=Path, help='Cypher file to validate.')
    parser.add_argument('--parameters', type=Path, help='JSON object with query parameters.')
    parser.add_argument('--max-hops', type=int, default=DEFAULT_MAX_HOPS)
    parser.add_argument('--max-limit', type=int, default=200)
    args = parser.parse_args()
    if args.max_hops <= 0 or args.max_limit <= 0:
        parser.error('Numeric limits must be positive.')
    parameters = None
    if args.parameters:
        parameters = json.loads(args.parameters.read_text(encoding='utf-8'))
    try:
        if args.plan:
            result = compile_plan(json.loads(args.plan.read_text(encoding='utf-8')),
                                  max_hops=args.max_hops, max_limit=args.max_limit)
            output = {'query': result['cypher'], 'parameters': result['parameters']}
        else:
            checked = validate_cypher(args.cypher.read_text(encoding='utf-8'), parameters,
                                      max_hops=args.max_hops, max_limit=args.max_limit)
            output = {'query': checked['query'], 'parameters': checked['parameters']}
    except (UnsafeCypher, InvalidPlan) as exc:
        print(f'REJECTED: {exc}')
        raise SystemExit(1)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
