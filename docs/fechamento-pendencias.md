# Fechamento das pendências P01, P03 e P08

Data: 09/11/2026. As três pendências foram fechadas **como remissões contextuais da fonte**, sem acrescentar definições gerais ou alterar os 93 conceitos e as 16 relações do grafo.

## Aprovação recebida

O usuário declarou no chat: “Conferi e concordei com as modificações. Agora, passemos para a parte que faltou”. Essa aprovação foi registrada em data/review/user-approval-source-check-v1.json, vinculada aos hashes dos 26 conceitos ajustados, cinco conceitos adicionados e cópias de leitura da entrega anterior. Não foi ampliada para toda relação preexistente, avaliação independente ou decisões contextuais produzidas depois da mensagem.

## Decisões

| Pendência | Evidência | Decisão aplicada |
|---|---|---|
| P01 — esquema/modelo ER | D02_C001 chama o modelo de ER schema; D02_C007 remete entity relationship schema ao modelo | Registrar a remissão ao C_entity_relationship_data_model somente no contexto de D02. Não criar definição geral de esquema. |
| P03 — simples/monovalorado | D02_C003 e D02_C007 fazem a equivalência explicitamente | Permitir seguir a remissão para C_simple_attribute ao consultar D02, com atribuição à fonte; não criar alias global nem fundir conceitos automaticamente. |
| P08 — arquivo/relação | D09_C001 e D09_C003 utilizam file como remissão a relation | Permitir seguir a remissão a C_relation em D09. Não definir arquivo físico nem fundir C_table e C_relation. |

O fechamento administrativo dessas ocorrências não elimina as ressalvas conceituais das fontes. Fora dos documentos indicados, as referências não são aplicadas automaticamente.

## Arquivos e uso

- data/normalization/contextual-aliases-v1.json: termos, documentos, evidências literais com offsets, conceitos de referência e regras de escopo.
- scripts/resolve-contextual-alias.py: consulta o registro e valida seus hashes e evidências.
- data/review/contextual-pending-v1/decisions.json: decisões vinculadas às pendências originais.
- data/release/current.json: mantém os três arquivos do grafo e aponta para o novo registro auxiliar e a aprovação humana recebida.

Exemplos:

```powershell
python scripts/resolve-contextual-alias.py --term "ER schema" --document D02
python scripts/resolve-contextual-alias.py --term "single-valued attributes" --document D02
python scripts/resolve-contextual-alias.py --term "file" --chunk D09_C003
python scripts/resolve-contextual-alias.py --term "FD" --chunk D05_C002
```

Os três primeiros retornam status contextual_reference, conceitos de referência e as ressalvas da fonte. Sem documento, retornam requires_document_context e nenhum conceito. Documento incompatível não resolve a referência. Todas as respostas preservam auto_merge_nodes=false. A exceção FD em D05_C002 retorna requires_review, sem mapear automaticamente para dependência funcional; documento D05 sem chunk exige mais contexto.

## Como integrar na parte 2

Importar somente primary_files do índice atual como fatos do grafo. O registro contextual é auxiliar para recuperação e desambiguação: quem implementar a busca pode consultá-lo antes de usar aliases gerais. Ele retorna referências para encontrar o contexto, sem autorizar MERGE entre conceitos ou criar arestas de equivalência. Ainda não está integrado a um serviço Neo4j ou interface de perguntas.

Não incluir as expressões do registro em Concept.aliases de forma global. Se uma busca trouxer a referência contextual, a resposta deve atribuir o uso ao documento: por exemplo, “Neste capítulo, a fonte usa file como outro nome para relação”.

## O que permanece aberto

Os quatro problemas originais de corpus/metadata/figure_source_issues.json, duas transcrições parciais, os riscos de aumentação/reflexividade e a expansão de cobertura continuam documentados. Não há definição externa de arquivo físico, esquema ou atributo monovalorado inserida nesta etapa. Se o grupo quiser definições gerais além do recorte da fonte, será necessária nova evidência e nova revisão.

A base segue com 93 conceitos e 16 relações. Restam a publicação desta atualização no GitHub e a integração ao Neo4j pela pessoa 2; o grafo ainda não foi executado nesta etapa.

## Validação

Os 65 testes passaram, incluindo casos sem contexto, contexto incompatível, referências por chunk, exceção FD e alteração de hash das fontes. Os três arquivos principais permanecem idênticos aos aprovados pelo usuário; não houve mudança nas contagens ou nas evidências do grafo.
