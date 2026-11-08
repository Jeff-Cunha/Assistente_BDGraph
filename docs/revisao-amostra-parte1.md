# Revisão da amostra para entrega à parte 2

Revisão de correspondência e do modelo de integração, feita por Codex em 8 de novembro de 2026. Sem revisão humana independente e sem execução de modelo nesta etapa.

## Ajustes efetuados

- Mantidos os 12 concept_ids e 9 relation_ids, sem alteração do contrato JSON 0.1.0.
- Ampliadas as citações de restrição, restrição de integridade, integridade de entidade, chaves, integridade referencial e junções externas para que tragam contexto suficiente, e não somente um pronome ou uma oração isolada.
- A relação REQUIRES entre integridade de entidade e chave primária preserva o parágrafo e registra que é uma regra do modelo conceitual exposta na fonte, sem declarar impossibilidade técnica de tabela física sem PK.
- A relação GOVERNS mantém a alternativa nula e a validade de referência como contexto da formulação da fonte.
- A evidência de outer join → HAS_FORM → left outer join agora inclui a passagem que nomeia ambas as formas, incluindo o exemplo SQL intermediário.
- Mantido TYPICALLY_USED_IN para chaves e JOIN: uso típico não é dependência obrigatória.
- Definidas a direção de SUPPLEMENTS e a derivação de MENTIONS a partir de todas as evidências relevantes.
- Explicitado que conceitos também preservam citações, além das relações.

## Verificação

A amostra permanece com 21 referências a citações, todas literais nos três trechos identificados. A validade sintática e referencial será novamente verificada antes do empacotamento. Não se acrescentaram nós ou relações para completar artificialmente a cobertura.

## Pendências preservadas

- Revisão humana da amostra e discussão do contrato com a pessoa 2.
- Revisão conceitual das divergências do corpus, em etapa posterior.
- Extração automática completa e validação de qualidade.
- Ingestão e teste no Neo4j, responsabilidade da parte 2.

O pacote de entrega inclui fontes e atribuições. Não inclui .env, chave Gemini, instaladores do Ollama, arquivos de trabalho ou resultados de tentativas de API.
