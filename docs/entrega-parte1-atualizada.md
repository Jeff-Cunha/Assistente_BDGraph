# Entrega atualizada da base para a parte 2

Atualização de 09/11/2026: modificações anteriores aprovadas pelo usuário e pendências P01/P03/P08 fechadas como remissões contextuais das fontes. O pacote permite iniciar ou ampliar a ingestão no Neo4j; não contém banco pronto, interface de perguntas ou modelo instalado no computador de quem recebe.

## Comece por estes arquivos

1. data/release/current.json: índice da versão atual, caminhos, métodos e hashes dos três arquivos principais.
2. docs/fechamento-pendencias.md: fechamento das três remissões contextuais e aprovação recebida. A revisão dos 26 resumos e cinco conceitos está em docs/revisao-fontes-2026-11-09.md.
3. docs/contrato-extracao.md: propriedades, relações estruturais e tipos semânticos permitidos.
4. corpus/metadata/sources.json e corpus/chunks/chunks.jsonl + figure_supplements.jsonl: documentos, trechos e evidências originais.

| Arquivo principal | Origem | Conceitos | Relações |
|---|---|---:|---:|
| data/extraction/rule-knowledge-union-v2/extraction.json | Extração por regras, com curadoria dos resumos | 79 | 5 |
| data/extraction/model-knowledge-union-v3/extraction.json | Propostas do LLM, com curadoria dos resumos | 20 | 11 |
| data/extraction/manual-source-review-v1/extraction.json | Cinco conceitos por curadoria manual assistida por IA | 5 | 0 |

Em conjunto: **93 IDs de conceito e 16 triplas semânticas únicas**. Não somar 79+20+5 como se fossem nós distintos. Fazer upsert por ID e reunir aliases/evidências, preservando o método de cada arquivo. As relações atuais não foram alteradas nesta revisão e nenhum fato novo foi atribuído ao LLM.

O corpus continua com nove documentos e 59 trechos (31 originais e 28 suplementos). corpus/reading é somente uma versão visual para leitura e não cria nove novos documentos ou novos chunks.

## Ingestão

Usar schemas/extraction.schema.json, com suporte a 0.1.0/0.1.1/0.1.2 e aos tipos SQL de docs/cobertura-sql.md. Preservar IDs estáveis, evidências, review_note, origem e relações estruturais. Não usar arquivos de corpus/reading como evidência.

```powershell
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/rule-knowledge-union-v2/extraction.json
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/model-knowledge-union-v3/extraction.json
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/manual-source-review-v1/extraction.json
```

Carregar somente os três arquivos de primary_files no índice atual. Pastas históricas contêm versões anteriores, propostas incorretas, testes sintéticos e respostas rejeitadas. Não importar recursivamente data/extraction. A amostra manual inicial sample.json continua opcional e fora desses totais; se já foi importada, deduplicar IDs/triplas e preservar evidências, sem substituir os resumos atuais por antigos.

Para quem já carregou a versão de 88 conceitos: atualizar as propriedades/evidências dos mesmos IDs, acrescentar os cinco conceitos novos e preservar as 16 relações. Os cinco conceitos novos ainda não possuem relações semânticas nesta entrega; não inventá-las na ingestão.

## Revisão e limitações

O usuário aprovou as 26 modificações e os cinco conceitos acrescentados da entrega anterior; o registro está em data/review/user-approval-source-check-v1.json. Não se presume revisão independente de todos os fatos. P01, P03 e P08 foram fechados como remissões contextuais verificadas por Codex; consulte docs/fechamento-pendencias.md. As ambiguidades de FD e as equivalências de D02/D09 exigem contexto; consultar data/review/contextual-pending-v1/source-cautions.json e as review_notes dos conceitos. Os quatro problemas originais das fontes e duas transcrições parciais foram preservados.

A pessoa 2 implementará Neo4j, restrições, índices, ingestão idempotente e consultas de verificação. Modelo/dimensão de embeddings precisam ser combinados com a recuperação. Não foram criados embeddings, consultas de produção ou uma avaliação independente das respostas.

## Leitura e pacote

Para leitura humana, usar corpus/reading/D01.md até D09.md; as tabelas de normalização estão em corpus/reading/D05.md. O pacote atualizado é outputs/entrega-parte1-pendencias-concluidas.zip. Os pacotes anteriores permanecem históricos. O registro data/normalization/contextual-aliases-v1.json é auxiliar à busca, não um quarto arquivo de fatos a importar no grafo. Não converter suas remissões em aliases globais ou fusões de nós.

Os 65 testes passaram e as três extrações foram validadas em estrutura e citações. Isso não comprova correção universal das fontes nem redução de alucinações do sistema final.
