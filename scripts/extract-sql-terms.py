"""Find reviewed SQL vocabulary in source pages; no semantic edges or query execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
# Curated names/summaries, independent of occurrence detection. Original quotes stay unchanged.
TERMS = [
 ('select','SELECT','consulta SELECT',r'\bSELECT\b','Consulta usada para recuperar dados de tabelas.'),
 ('from','FROM','cláusula FROM',r'\bFROM\b','Cláusula que indica as fontes de dados nos exemplos de consulta.'),
 ('where','WHERE','cláusula WHERE',r'\bWHERE\b','Cláusula que seleciona linhas por uma condição; a fonte explica sua aplicação antes da agregação.'),
 ('group_by','GROUP BY','cláusula GROUP BY',r'\bGROUP\s+BY\b','Cláusula usada nos exemplos para formar grupos sobre os quais agregações são calculadas.'),
 ('having','HAVING','cláusula HAVING',r'\bHAVING\b','Cláusula que filtra linhas de grupos após o agrupamento e a agregação; não exige sempre uma função agregadora.'),
 ('order_by','ORDER BY','cláusula ORDER BY',r'\bORDER\s+BY\b','Cláusula usada para ordenar os resultados nos exemplos.'),
 ('distinct','DISTINCT','modificador DISTINCT',r'\bDISTINCT\b','Modificador usado para remover linhas duplicadas do resultado, sem garantir ordenação por si só.'),
 ('as','AS','cláusula AS',r'\bAS\b','Palavra usada para atribuir outro nome a uma coluna de saída nos exemplos.'),
 ('count','count','função COUNT',r'\bcount\b','Função agregadora de contagem apresentada nos exemplos com count(*).'),
 ('sum','sum','função SUM',r'\bsum\b','Função de soma citada pela fonte entre as funções agregadoras.'),
 ('avg','avg','função AVG',r'\bavg\b','Função de média citada pela fonte entre as funções agregadoras.'),
 ('max','max','função MAX',r'\bmax\b','Função que calcula um máximo nos exemplos de agregação.'),
 ('min','min','função MIN',r'\bmin\b','Função de mínimo citada pela fonte entre as funções agregadoras.'),
 ('filter','FILTER','opção FILTER',r'\bFILTER\b','Opção que seleciona entradas de uma função agregadora específica, sem filtrar necessariamente as demais.'),
 ('like','LIKE','operador LIKE',r'\bLIKE\b','Operador de correspondência de padrões citado na explicação dos exemplos.'),
 ('and','AND','operador AND',r'\bAND\b','Operador booleano permitido nas condições de seleção da fonte.'),
 ('or','OR','operador OR',r'\bOR\b','Operador booleano permitido nas condições de seleção da fonte.'),
 ('not','NOT','operador NOT',r'\bNOT\b','Operador booleano permitido nas condições de seleção da fonte.'),
 ('join','join','junção',r'\bjoin\b','Operação que combina linhas de tabelas conforme uma expressão.'),
 ('inner_join','inner join','junção interna',r'\binner joins?\b','Forma de junção identificada na comparação com as junções externas da fonte.'),
 ('outer_join','outer join','junção externa',r'\bouter joins?\b','Forma de junção que representa ausência de correspondência com valores nulos, conforme os exemplos.'),
 ('left_outer_join','left outer join','junção externa à esquerda',r'\bleft (?:outer )?joins?\b','Junção que preserva as linhas da tabela à esquerda, conforme a descrição da fonte.'),
]


def find_occurrences(chunks, terms=TERMS):
    found = []
    for c in chunks:
        if c['document_id'] not in ('D06', 'D07', 'D08'):
            continue
        blocks = list(re.finditer(r'[^\n]+(?:\n(?!\n)[^\n]+)*', c['text']))
        for slug, name, pt, pattern, description in terms:
            flags = re.I if slug in ('count','sum','avg','max','min','join','inner_join','outer_join','left_outer_join') else 0
            match = re.search(pattern, c['text'], flags)
            if match is None:
                continue
            block = next(b for b in blocks if b.start() <= match.start() < b.end())
            found.append({'concept_id': 'C_' + slug, 'canonical_name': name,
                'name_pt': pt, 'description_pt': description, 'category': 'operation',
                'surface': match.group(), 'chunk_id': c['chunk_id'], 'document_id': c['document_id'],
                'start': block.start(), 'end': block.end(), 'quote': block.group(),
                'match_start': match.start(), 'match_end': match.end(), 'source_url': c['source_url'],
                'code_context': block.group().lstrip().startswith('```'),
                'note': 'Vocabulary occurrence, not certification that an example query is valid or that a result is correct.'})
    return found


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not args.output.resolve().is_relative_to(ROOT) or (args.output.exists() and any(args.output.iterdir())):
        p.error('Choose a new empty directory inside project.')
    raw = (ROOT / 'corpus/chunks/chunks.jsonl').read_bytes()
    chunks = [json.loads(x) for x in raw.decode('utf-8').splitlines() if x.strip()]
    entries = find_occurrences(chunks)
    args.output.mkdir(parents=True)
    (args.output / 'occurrences.jsonl').write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in entries), encoding='utf-8')
    manifest = {'input_sha256': hashlib.sha256(raw).hexdigest(), 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'method': 'reviewed_sql_vocabulary_rules', 'concepts': len({e['concept_id'] for e in entries}),
                'occurrences': len(entries), 'note': 'Curated vocabulary and summaries; source occurrences detected by rules. Semantic edges are not generated.'}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Found {manifest['concepts']} SQL concepts in {len(entries)} chunk occurrences; no relations generated.")


if __name__ == '__main__':
    main()
