> Atualização de 09/11/2026: este texto registra uma etapa anterior. A referência atual de integração é data/release/current.json: 93 conceitos únicos, 16 relações e três arquivos principais. Consulte docs/revisao-fontes-2026-11-09.md para os resumos corrigidos e pendências resolvidas. As descrições antigas abaixo não substituem a revisão atual.

# Revisão dos glossários e nomes equivalentes

Esta etapa revisou as definições extraídas das fontes, curou nomes e resumos em português e preservou os IDs já utilizados. Não foram criadas relações semânticas novas. A revisão foi realizada por Codex, sem conferência humana independente.

## Correção da extração

O parser anterior produzia 72 entradas porque três pares de definições estavam adjacentes dentro de um mesmo parágrafo. A regra foi corrigida para separar os marcadores de definição sem alterar o texto original. Foram recuperados candidate key, DBA e attribute como entradas próprias; as citações de alternate key, Armstrong’s axioms e atomic value deixaram de conter a definição vizinha.

O corpus e as saídas antigas não foram modificados. A nova versão em data/extraction/glossary-v3 contém 75 ocorrências. Cada uma tem ID, trecho, offsets, URL e citação literal.

## Resultado da revisão

| Decisão por ocorrência | Quantidade |
|---|---:|
| Aproveitada para conceitos revisados | 64 |
| Em dúvida, não exportada | 8 |
| Fora do recorte, não exportada | 3 |

As 64 ocorrências aproveitadas resultam em 56 conceitos canônicos. Os aliases registram formas plurais, siglas e nomes equivalentes, preservando todos os rótulos originais. Os resumos em português são curadoria separada das citações em inglês; não devem ser apresentados como tradução literal da fonte.

Exemplos de resolução:

- FK e foreign key (FK) → C_foreign_key.
- constraints e constraint → C_constraint.
- derived entities → dependent entity, conforme remissão explícita no glossário.
- kernel → independent entity, apenas no contexto de entidades de banco de dados desta fonte.
- recursive relationship → unary relationship, conforme remissão do glossário.
- column e field → attribute, como equivalência lexical no glossário relacional; não uma identidade universal entre níveis de modelagem.
- row, record e tuple → C_row, no contexto relacional adotado. Um ID C_record de um piloto local antigo é apontado como possível redirecionamento; nenhum arquivo antigo ou banco foi migrado automaticamente.

Não foram fundidos dependent (de uma dependência funcional) e dependent entity. Tabela e relação formal também mantêm IDs diferentes, ainda que a fonte os relacione terminologicamente. Não houve agrupamento apenas por semelhança de palavras.

## Itens em dúvida

Foram preservados com status flag, fora do JSON aprovado:

- entity relationship schema: remissão que pode confundir esquema e modelo.
- n-ary: definição da aridade formulada em termos de tabelas, a revisar.
- single-valued attributes: não foi equiparado automaticamente a simple attribute.
- ternary relationship: definição restrita a muitos-para-muitos, a revisar.
- decomposition: descrição como regra prática, não definição geral.
- Union: sentido ambíguo entre dependências, combinação de tabelas e SQL.
- second normal form (2NF): o resumo limita a definição a PK de um atributo; o próprio capítulo também discute chave composta sem dependência parcial.
- file: remissão contextual a relation, pendente para evitar confusão com arquivo físico.

As referências a essas definições permanecem no corpus. Não foram corrigidas silenciosamente nem removidas dos documentos. EID e SIN foram excluídos desta camada por serem identificadores dos exemplos. BCNF foi preservada na fonte, mas excluída do recorte inicial até 3FN.

## Arquivos para integração

- data/extraction/glossary-v3/concepts-reviewed.json: 56 conceitos, 64 evidências, sem relações semânticas.
- data/extraction/glossary-v3/review-decisions.json: decisão para todas as 75 ocorrências, mapeamentos, nomes portugueses e hash da entrada revisada.
- data/extraction/glossary-v3/concept-definitions.jsonl: candidatos extraídos, inclusive os não aprovados.
- schemas/extraction.schema.json: compatível com 0.1.0 e extensão 0.1.1.

O método é rule_candidates e a versão é 0.1.1. A estrutura de propriedades não mudou; apenas se identifica honestamente a extração por regras. O validador antigo do GitHub precisa receber o esquema atualizado antes de validar essa saída. As extrações por LLM continuam separadas em data/extraction/reviewed-union-v1/extraction.json.

Os 56 conceitos de glossário e os nove da união derivada de LLM têm **61 IDs únicos em conjunto**, com compatibilidade de nomes canônicos e categorias verificada. As cinco relações semânticas da união anterior não foram alteradas. Ao carregar ambos no Neo4j, fazer upsert por ID e reunir evidências; não somar as contagens como se fossem nós distintos. Não existe ainda um único arquivo misturando as duas origens, para preservar a proveniência.

## Reproduzir e conferir

```powershell
python scripts/extract-glossary-concepts.py --output data/extraction/glossary-v4
python scripts/export-glossary-review.py --candidates data/extraction/glossary-v3/concept-definitions.jsonl --review data/extraction/glossary-v3/review-decisions.json --output data/extraction/glossary-v3/concepts-reviewed-v2.json
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/glossary-v3/concepts-reviewed-v2.json
python -m unittest discover -s tests -p "test_*.py" -v
```

A revisão fica vinculada ao hash da entrada. Não reaplicar decisões antigas se os candidatos forem alterados; conferir os novos resultados antes. As saídas existentes não são sobrescritas.

Foram executados 41 testes e a saída revisada passou no validador: 56 conceitos, zero relações e 64 evidências literais. Também se verificou a compatibilidade de IDs com a amostra manual e com os fatos derivados do modelo.

## Limitações restantes

Esta entrega amplia a camada de conceitos, mas não representa extração completa das relações dos nove documentos. D06 e D08 não têm o formato de glossário usado pela regra. As pendências de definições, fontes e figuras continuam registradas. A revisão não garante verdade universal das formulações didáticas das fontes, nem substitui avaliação independente do sistema.
