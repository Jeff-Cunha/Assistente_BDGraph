# Entrega atualizada da base para a parte 2

O pacote contém o corpus, o código de preparação/extração, revisões e dados para iniciar ou ampliar a ingestão no Neo4j. Não contém um banco pronto, interface de perguntas ou modelo instalado no computador de quem recebe.

## Comece por estes arquivos

1. docs/cobertura-sql.md: resultados atuais, tipos de relação SQL e limitações.
2. docs/contrato-extracao.md: estrutura dos dados e extensões compatíveis 0.1.1/0.1.2.
3. corpus/metadata/sources.json e os dois JSONL em corpus/chunks: documentos e trechos.
4. data/extraction/rule-knowledge-union-v1/extraction.json: conceitos e relações por regras, revisados.
5. data/extraction/model-knowledge-union-v2/extraction.json: conceitos e relações derivados de LLM, revisados.

As duas saídas atuais têm, em conjunto, 88 IDs de conceito e 16 triplas semânticas diferentes. Carregar com upsert, reunindo aliases e evidências dos IDs compartilhados. Preservar a origem por arquivo ou metadado da carga: não apresentar tudo como geração do LLM. O corpus continua com 9 documentos e 59 trechos (31 originais e 28 suplementos).

A amostra manual data/extraction/sample.json é um terceiro material opcional de desenvolvimento, não parte dos totais acima. Se já foi carregada, não precisa ser apagada: deduplicar triplas e reunir as evidências. Caso seja mantida com as duas saídas, os IDs de conceitos continuam compatíveis; conferir as contagens das arestas após deduplicação.

## Mudança necessária no validador e na ingestão

Usar schemas/extraction.schema.json deste pacote. Ele aceita os arquivos antigos e identifica origem por regras e tipos SQL. A forma das propriedades de Document/Chunk/Concept e das evidências não mudou. Atualizar a lista permitida de tipos na ingestão com os seis tipos SQL descritos em docs/cobertura-sql.md; não interpolar tipos arbitrários vindos de textos ou respostas.

```powershell
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/rule-knowledge-union-v1/extraction.json
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/model-knowledge-union-v2/extraction.json
```

Somente os arquivos aprovados devem compor o conhecimento aceito da aplicação. Diretórios históricos contêm candidatos incorretos, testes sintéticos e respostas rejeitadas; não carregar recursivamente todo data/extraction como fatos. Os controles são identificados e ficaram fora das saídas.

## Responsabilidades e pendências

A pessoa 2 implementará Neo4j, restrições, índices, ingestão idempotente e consultas de verificação. Modelo/dimensão de embeddings precisam ser combinados com a recuperação. Não foram inventados embeddings ou afirmada conclusão dos índices.

O material foi revisado por Codex, sem conferência humana independente. Há definições e relações sinalizadas, problemas nas fontes e duas transcrições parciais preservadas. A extração ainda tem cobertura limitada e exige avaliação independente. O objetivo deste pacote é permitir integração verificável, sem ocultar essas limitações.
