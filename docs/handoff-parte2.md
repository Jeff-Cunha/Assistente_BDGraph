# O que a parte 2 entrega para as partes 3, 4, 5 e 6

Resumo prático. Detalhes do modelo: [modelo-grafo.md](modelo-grafo.md). Consultas prontas: `db/consultas-exemplo.cypher`.

## Para todos: ligar o banco

```bash
cd <pasta do repo> && bash scripts/setup-neo4j.sh     # macOS/Linux; precisa do Docker Desktop aberto
```

Cria o `.env` com senha local, sobe o Neo4j, carrega o grafo e confere. Conexão (variáveis no `.env`): `NEO4J_URI=bolt://localhost:7687`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`. Neo4j Browser: http://localhost:7474 (use Chrome ou Firefox; o Safari bloqueia a conexão local). Se o Chrome traduzir a página, os nomes de nós e relações aparecem em português; os nomes reais estão em inglês.

Sem Docker (por exemplo, no Windows sem Docker Desktop), é possível usar Neo4j Aura Free: coloque o endereço `neo4j+s://...` e a senha no `.env` e rode `python scripts/neo4j_ingest.py schema` e depois `... ingest --include-sample`. Esse caminho **não foi testado** pela parte 2.

Tamanho atual: 9 Document, 59 Chunk, 93 Concept, 23 relações semânticas (com `--include-sample`).

## Parte 3 (recuperação)

- **Texto para embeddings:** `Chunk.text` (59 trechos: 31 `page_text` e 28 `figure_transcription`). Em inglês, com HTML inline preservado.
- **Índice vetorial ainda não existe.** Precisamos que você decida modelo e dimensão. Depois rodamos o comando comentado no fim de `db/schema.cypher`, com `Chunk.embedding`.
- **Reingestão não apaga `embedding`**: pode gravar os vetores e rodar `ingest` de novo sem perdê-los (testado).
- **Busca de conceito por nome** (inglês, português ou alias; ignora acentos): `CALL db.index.fulltext.queryNodes('concept_names', 'restricao')`, usada pela interface para sugerir conceitos quando o nome não casa palavra por palavra. O texto dos trechos não tem índice fulltext: a busca neles é vetorial (`chunk_embedding`).
- **Multi-hop com evidência por aresta:** cada relação semântica tem `evidence_chunk_ids`; consulta 4 do arquivo de exemplos.
- **Algoritmo de grafo:** a edição Community suporta o plugin GDS (há uma linha comentada em `docker-compose.yml`), mas o grafo ainda é pequeno e esparso (23 relações). Avise se for usar GDS.

## Parte 4 (LLM e Cypher)

- **Esquema para o prompt:** labels `Document`, `Chunk`, `Concept`; relações estruturais `CONTAINS`, `SUPPLEMENTS`, `MENTIONS`; tipos semânticos permitidos: IS_A, SUPPORTS, REQUIRES, GOVERNS, TYPICALLY_USED_IN, COMBINES, HAS_FORM, PRESERVES, RETRIEVES, FILTERS, GROUPS, AGGREGATES, EVALUATED_BEFORE, REMOVES_DUPLICATES. Hoje existem 10 deles no banco.
- **Identidade:** sempre por `concept_id`, `chunk_id`, `document_id`. Nomes em português ou inglês não são chaves.
- **Segurança do Cypher gerado.** Use `session.execute_read(...)` (ou `default_access_mode=READ`): o Neo4j recusa `CREATE`, `SET` e `DELETE` nesse modo, com erro `Neo.ClientError.Statement.AccessMode` (testado). A Community não tem usuários só-leitura, então esta é a barreira do banco. Ela **não** substitui validar o texto (lista de cláusulas permitidas) nem limitar `LIMIT` e tempo de execução.
- **Dizer "não sei":** só afirme o que tiver evidência. Cada aresta traz `evidence_chunk_ids` e `evidence_quotes_json` (citações literais). `review_status` não é probabilidade de acerto; não o use como "confiança calibrada".
- **Cuidado semântico:** `TYPICALLY_USED_IN` significa "tipicamente usado em", não obrigação. Não existe aresta `JOIN REQUIRES chave estrangeira`, e o sistema não deve afirmar isso.

## Parte 5 (interface e grafo)

- **Subgrafo para desenhar:** `MATCH p = (:Concept {concept_id: $id})-[*1..3]->(:Concept) RETURN p`.
- **Rótulo do nó:** `name_pt` (ou `canonical_name`); cor por `category` (general, structure, constraint, operation, normalization).
- **Painel de fontes:** `Chunk.text`, `Chunk.document_id`, `Chunk.source_url`; título, versão e licença em `Document` (`title`, `version`, `license_name`, `license_url`, `attributions_and_notices`). Preserve a atribuição ao mostrar trechos.
- **Detalhe do conceito:** `description_pt`, `aliases`, `review_status`, `review_note`; citações em `evidence_quotes_json` (texto JSON; faça `JSON.parse`).
- **Pendências visíveis:** trechos de figura com `transcription_status = 'partial'` ou `source_issue_ids` não vazio merecem um aviso (consulta 7).
- Textos dos trechos estão em inglês; a interface deve permitir perguntas em português.

## Parte 6 (avaliação e integração)

- **Reprodução:** `bash scripts/setup-neo4j.sh`, depois `python scripts/neo4j_ingest.py verify --include-sample` (deve terminar com todas as linhas `[OK]`). Testes: `python -m unittest discover -s tests` e, com o banco no ar, `NEO4J_TEST=1 python -m unittest tests.test_neo4j_ingest`.
- **O que o grafo consegue responder hoje:** só 23 relações semânticas. Os caminhos que cruzam documentos passam por FK (D03) → JOIN → inner/outer/left outer join e linha/tabela (D07). Perguntas multi-hop fora disso provavelmente não terão caminho, o que serve como teste de "sem evidência suficiente", mas não como acerto.
- Perguntas de teste devem listar o `chunk_id` esperado como evidência; todo conceito e relação aponta para eles.
- Sem `--include-sample` o grafo tem só 16 relações e nenhum caminho entre documentos.
