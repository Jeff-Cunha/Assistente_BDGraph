// Consultas de exemplo e de verificação. Cole uma por vez no Neo4j Browser (http://localhost:7474)
// ou rode o arquivo inteiro:  cypher-shell -u neo4j -p <senha> -f db/consultas-exemplo.cypher

// 1) Contagem por tipo de nó
MATCH (n) RETURN labels(n)[0] AS tipo, count(n) AS qtd ORDER BY tipo;

// 2) Busca por nome de conceito (inglês, português ou alias; ignora acentos)
CALL db.index.fulltext.queryNodes('concept_names', 'restricao') YIELD node, score
RETURN node.concept_id AS id, node.name_pt AS nome, score ORDER BY score DESC LIMIT 5;

// 3) Em quais trechos (e documentos) a chave estrangeira é mencionada?
MATCH (c:Chunk)-[:MENTIONS]->(:Concept {concept_id: 'C_foreign_key'})
RETURN c.document_id AS documento, c.chunk_id AS trecho, c.content_type AS tipo ORDER BY trecho;

// 4) Multi-hop: de 2 a 3 saltos a partir de chave estrangeira, com a evidência de CADA aresta
MATCH p = (:Concept {concept_id: 'C_foreign_key'})-[*2..3]->(:Concept)
RETURN [n IN nodes(p) | n.concept_id] AS caminho,
       [r IN relationships(p) | type(r)] AS tipos,
       [r IN relationships(p) | r.evidence_chunk_ids] AS evidencias
ORDER BY size(relationships(p)), caminho;

// 5) Caminho que reúne dois documentos (precisa da carga com --include-sample)
MATCH p = (:Concept {concept_id: 'C_foreign_key'})-[*2..3]->(:Concept)
WITH p, [r IN relationships(p) | r.evidence_chunk_ids] AS ev
UNWIND ev AS lista UNWIND lista AS trecho
WITH p, collect(DISTINCT split(trecho, '_')[0]) AS documentos
WHERE size(documentos) > 1
RETURN [n IN nodes(p) | n.concept_id] AS caminho, documentos;

// 6) De onde veio cada fato? Métodos de extração e status de revisão das relações
MATCH (a:Concept)-[r]->(b:Concept)
WHERE r.relation_id IS NOT NULL
RETURN a.concept_id AS origem, type(r) AS tipo, b.concept_id AS destino,
       r.extraction_methods AS metodos, r.review_status AS revisao ORDER BY tipo, origem;

// 7) Transcrições de figuras parciais ou com pendência de fonte (continuam identificáveis)
MATCH (c:Chunk {content_type: 'figure_transcription'})
WHERE c.transcription_status <> 'complete' OR size(c.source_issue_ids) > 0
RETURN c.chunk_id AS trecho, c.transcription_status AS status, c.source_issue_ids AS pendencias_fonte;
