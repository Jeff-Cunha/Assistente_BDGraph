// Esquema do grafo do Assistente_BDGraph (Neo4j 5.x, edição Community).
// Aplicar com:  python scripts/neo4j_ingest.py schema
// Todos os comandos usam IF NOT EXISTS: podem ser repetidos sem erro.
//
// Labels:  Document, Chunk, Concept
// Chaves:  document_id, chunk_id, concept_id (únicas)

// --- Restrições de unicidade (também criam um índice na propriedade) ---
CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.document_id IS UNIQUE;
CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE;
CREATE CONSTRAINT concept_id_unique IF NOT EXISTS FOR (c:Concept) REQUIRE c.concept_id IS UNIQUE;

// --- Índices de propriedade (filtros frequentes das consultas da Pessoa 3 e 4) ---
CREATE INDEX chunk_document_id IF NOT EXISTS FOR (c:Chunk) ON (c.document_id);
CREATE INDEX chunk_content_type IF NOT EXISTS FOR (c:Chunk) ON (c.content_type);
CREATE INDEX concept_category IF NOT EXISTS FOR (c:Concept) ON (c.category);
CREATE INDEX concept_canonical_name IF NOT EXISTS FOR (c:Concept) ON (c.canonical_name);

// --- Índices de texto (fulltext) ---
// Nomes de conceito: inglês, português e aliases; standard-folding ignora acentos
// (buscar "restricao" encontra "restrição").
CREATE FULLTEXT INDEX concept_names IF NOT EXISTS
FOR (c:Concept) ON EACH [c.canonical_name, c.name_pt, c.aliases]
OPTIONS {indexConfig: {`fulltext.analyzer`: 'standard-folding'}};

// Texto dos trechos (evidências originais, em inglês).
CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS
FOR (c:Chunk) ON EACH [c.text];

// --- Índice vetorial: NÃO criado aqui de propósito ---
// Depende do modelo de embeddings e da dimensão, que a Pessoa 3 ainda vai definir.
// Quando definirem, o comando será (trocar <DIM> pela dimensão do modelo):
//
//   CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
//   FOR (c:Chunk) ON (c.embedding)
//   OPTIONS {indexConfig: {`vector.dimensions`: <DIM>, `vector.similarity_function`: 'cosine'}};
