# Contrato de extração e integração

Versão: 0.1.0. Estado: referência revisada para a entrega inicial à parte 2; alterações posteriores devem ser combinadas entre as partes.

Extensão 0.1.1: a estrutura de nós, evidências e relações permanece igual; o esquema atualizado também aceita `extraction_method=rule_candidates` para extração por regras de glossário, exigindo versão 0.1.1 nesse caso. A versão 0.1.0 e suas amostras permanecem válidas. Usar o esquema atualizado ao validar as novas saídas; não identificar extração por regras como saída de LLM. Consulte docs/revisao-glossarios.md.

Extensão 0.1.2: acrescenta os tipos SQL RETRIEVES, FILTERS, GROUPS, AGGREGATES, EVALUATED_BEFORE e REMOVES_DUPLICATES. Arquivos que utilizem esses tipos precisam informar 0.1.2. As versões e os tipos anteriores continuam válidos, e o formato das propriedades não mudou. A origem rule_candidates pode usar 0.1.1 ou 0.1.2. Consulte docs/cobertura-sql.md para sentidos e limites.

Este contrato define a saída da parte 1 e a entrada da ingestão da parte 2. A amostra em `data/extraction/sample.json` foi construída manualmente para validar formato e rastreabilidade; não constitui uma extração automática nem uma avaliação independente.

## Entradas

- `corpus/metadata/sources.json`: documentos e proveniência.
- `corpus/chunks/chunks.jsonl`: 31 trechos originais.
- `corpus/chunks/figure_supplements.jsonl`: 28 suplementos, carregados separadamente com seus metadados e limites de legibilidade.
- `corpus/metadata/figure_source_issues.json`: pendências das fontes, preservadas para revisão posterior.

Não alterar esses arquivos para acomodar o extrator. Trabalhar sobre cópias em memória. Textos em inglês continuam sendo evidências originais; traduções e definições sintetizadas nunca devem ser apresentadas como citações literais.

## Modelo LPG inicial

| Nó | Identificador | Propriedades principais |
|---|---|---|
| Document | document_id, herdado do corpus | title, source_url, language, version |
| Chunk | chunk_id, herdado do corpus | text, content_type, document_id, section_path |
| Concept | concept_id, atribuído por registro canônico | canonical_name, name_pt, aliases, category, description_pt, review_status |

Relações estruturais: `(Document)-[:CONTAINS]->(Chunk)` e `(Chunk)-[:MENTIONS]->(Concept)`. Documentos e trechos são carregados do corpus, não gerados pelo LLM. Para suplementos, preservar `figure_ids` e `parent_chunk_ids`; vincular ao documento e aos trechos-pai por `SUPPLEMENTS`.

Direção definida de SUPPLEMENTS: `(suplemento:Chunk)-[:SUPPLEMENTS]->(trechoPai:Chunk)`. O documento contém também o suplemento por CONTAINS. MENTIONS é criado para cada par único trecho/conceito encontrado nas evidências dos conceitos ou das relações (neste caso, os dois conceitos da aresta). Preservar as citações e não criar uma menção em todos os chunks apenas porque o documento trata do assunto.

Evidências dos próprios conceitos também devem ser preservadas em `evidence_chunk_ids` e `evidence_quotes_json` no Concept, além de `review_note`. MENTIONS permite travessia até o contexto; o JSON preserva as citações exatas. Não remover evidências ao atualizar propriedades de um nó existente.

Cada relação semântica será `(Concept)-[tipo]->(Concept)`, com `relation_id`, `evidence_chunk_ids`, `evidence_quotes_json`, `assertion_kind` e `review_status`. O JSON é serializado em string porque objetos aninhados não são propriedades diretas do Neo4j. No arquivo de troca, evidências continuam como objetos estruturados.

Uma relação pode ter diversas evidências e fontes. Não criar arestas duplicadas por evidência. A ingestão deve resolver por IDs estáveis, nunca apenas pelo nome traduzido. Reexecuções não devem duplicar nós ou relações.

## Conceitos e equivalência

- Categorias iniciais: `general`, `structure`, `constraint`, `operation`, `normalization`.
- Nome canônico em inglês e nome de exibição em português; aliases nos dois idiomas.
- IDs no padrão `C_foreign_key`. Não mudar IDs quando adicionar tradução ou alias.
- `PK` e `primary key` podem representar o mesmo conceito. `JOIN` e `INNER JOIN` permanecem distintos: um é geral e outro específico.
- Não fundir termos só por proximidade textual. Alias ambíguo deve ir para revisão.
- Tabelas e colunas de exemplos, como Customer.CustID, não são conceitos gerais. Nesta versão, manter seu contexto nas evidências e não promovê-las automaticamente a Concept. Uma expansão posterior pode introduzir Example, TableExample e ColumnExample com namespace do documento.

## Vocabulário inicial de relações

| Tipo | Sentido |
|---|---|
| IS_A | específico → categoria geral |
| SUPPORTS | modelo/sistema → recurso suportado |
| REQUIRES | conceito/regra → elemento exigido, com qualificações na evidência |
| GOVERNS | regra → elemento cujo comportamento regula |
| TYPICALLY_USED_IN | elemento → operação em que é tipicamente empregado; não significa obrigação |
| COMBINES | operação → estrutura combinada |
| HAS_FORM | operação geral → forma específica |
| PRESERVES | operação → elemento preservado |

O vocabulário será ampliado mediante justificativa e revisão. Arestas descrevem afirmações documentadas, não leis universais. Condições, negações e expressões como "may", "typically" e "must" devem ser preservadas. Não transformar coocorrência em relação.

## Evidência e revisão

Cada conceito e relação exige ao menos uma evidência: `chunk_id` e `quote` literal, não vazia, contida no campo `text` do trecho. Não remover HTML, traduzir ou normalizar espaços na citação durante a validação. Localizadores de caracteres podem ser adicionados depois.

`assertion_kind` é `explicit` ou `inferred`. Na primeira versão, aceitar apenas afirmações explícitas para o grafo de respostas. Inferências ficam em revisão e nunca entram silenciosamente na recuperação. Trechos adjacentes podem apoiar um caminho, mas isso não autoriza inventar uma nova aresta causal.

`review_status`: `pending`, `accepted` ou `flagged`. `accepted` significa revisão da correspondência com a evidência, não certificação de verdade universal. Registrar `review_note` quando necessário. Afirmações em conflito ou apoiadas em detalhes ilegíveis não podem ser aceitas automaticamente. Não é necessário resolver as inconsistências do corpus nesta etapa.

Não usar probabilidade inventada pelo LLM como confiança calibrada. O indicador de confiança da interface será definido separadamente; status de revisão não equivale a probabilidade de acerto.

## Saída

Um objeto JSON com `schema_version`, `extraction_method`, `input_chunk_ids`, `concepts` e `relations`, conforme `schemas/extraction.schema.json`. IDs de relação são persistidos no registro; a deduplicação considera origem, tipo e destino, reunindo evidências compatíveis.

O extrator automático deve inicialmente gerar candidatos por trecho. Um passo posterior resolve nomes equivalentes e atribui IDs canônicos antes da validação. Saída bruta do LLM não deve ser ingerida diretamente no banco.

## Amostra e verificação

Executar na raiz do projeto:

```powershell
pwsh -NoProfile -File scripts/validate-extraction.ps1
```

O verificador confere esquema, IDs, referências, citações literais e duplicidades estruturais. Ele não decide verdade conceitual, qualidade de tradução, suficiência da evidência nem segurança de Cypher. A amostra usa trechos de D03 e D07; não cobre todos os conceitos desses documentos.

## Próximas implementações

1. Revisar este contrato com os responsáveis por Neo4j e recuperação.
2. Escolher provedor/modelo e configurar credenciais locais fora do Git.
3. Implementar o extrator com `docs/prompt-extracao.md` e manter logs do modelo, parâmetros e versões.
4. Comparar os candidatos à amostra revisada sem tratar esta amostra como conjunto independente de avaliação.
5. Ingerir a saída validada e demonstrar um caminho entre conceitos com evidências.
