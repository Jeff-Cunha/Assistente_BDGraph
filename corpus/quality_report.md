# Relatório de qualidade

Verificação baseada nos HTML efetivamente baixados, sem substituição de fontes. Datas de coleta em UTC no manifesto. O texto do corpus permanece em inglês.

| ID | Palavras | Trechos | Tabelas HTML | Blocos pre + SQL textbox | Figuras (ocorrências) | Status |
|---|---:|---:|---:|---:|---:|---|
| D01 | 649 | 2 | 0 | 0 + 0 | 3 | passed_with_image_dependencies |
| D02 | 3753 | 8 | 0 | 0 + 0 | 15 | passed_with_image_dependencies |
| D03 | 2596 | 6 | 0 | 0 + 2 | 17 | passed_with_image_dependencies |
| D04 | 1250 | 3 | 0 | 0 + 0 | 7 | passed_with_image_dependencies |
| D05 | 1822 | 4 | 6 | 0 + 0 | 4 | passed_with_image_dependencies |
| D06 | 495 | 1 | 0 | 13 + 0 | 0 | passed |
| D07 | 941 | 2 | 0 | 10 + 0 | 0 | passed |
| D08 | 641 | 2 | 1 | 13 + 0 | 0 | passed |
| D09 | 1230 | 3 | 0 | 0 + 0 | 5 | passed_with_image_dependencies |

Total: 13377 palavras; 31 trechos; 9 documentos processados.

## Verificações executadas

- HTTP 200, seletor do conteúdo principal e título presentes; URLs finais e redirecionamentos registrados.
- Títulos, células de tabelas, blocos pre, legendas e fragmentos de texto visível confrontados com o DOM original; resultados detalhados em metadata/quality_checks.json.
- Todo o texto visível também comparado na ordem exata, desconsiderando apenas espaços; hierarquia dos títulos e sequência dos textos alternativos verificadas após renderização CommonMark.
- Blocos pre preservados literalmente, incluindo espaços e linhas de resultados SQL. Em D03, dois exemplos SQL eram textboxes com br e foram convertidos em blocos sql.
- Tabelas preservadas como HTML válido dentro do Markdown, sem criar cabeçalhos ausentes.
- Imagens locais verificadas por decodificação. Isso confirma arquivos válidos, não garante que todo texto pequeno da imagem seja legível.
- Junção dos textos dos chunks reconstrói cada Markdown exatamente: confirma cobertura completa e ausência de sobreposição.
- SHA-256 do HTML validado contra o registro da coleta. PostgreSQL restrito às URLs /docs/18/.

## Figuras e limitações

O corpus textual NÃO é uma transcrição completa dos diagramas/tabelas em imagens. As figuras foram preservadas em raw/assets e vinculadas no Markdown; legendas e alt originais estão em metadata/figures.json. Nenhum OCR ou interpretação foi inventado. Todos os elementos gráficos foram conservadoramente marcados como dependentes de consulta visual, inclusive símbolos inline.

Os originais do livro incluem exercícios, respostas/casos e exemplos além do SQL básico, como Transact-SQL em D03. Foram preservados por fidelidade às fontes solicitadas, sem gerar conteúdo sintético.

O chunking prefere seções de nível principal, combina seções curtas adjacentes, mantém unidades indivisíveis e não usa sobreposição. Nesta coleta, os 31 trechos ficaram entre 301 e 590 palavras; metadata/chunk_size_exceptions.json está vazio. IDs são determinísticos para os mesmos HTML e algoritmo; mudanças futuras no conteúdo podem deslocar índices.

Foi inspecionada uma folha de contato com as 50 imagens locais (metadata/figures_contact_sheet.jpg). Ela confirma a presença de diagramas, fórmulas, símbolos e tabelas em imagens; não equivale à transcrição nem à validação de cada caractere nelas.

Todas as nove páginas retornaram HTTP 200 na coleta direta e mantiveram a URL solicitada, sem redirecionamentos de documentos. Não houve troca de fontes. A verificação preliminar pela ferramenta web de D06 apresentou timeout; o download direto e os testes posteriores passaram.

## D01 — Chapter 2 Fundamental Concepts

- Figures retained locally with original captions/alt; graphical information not transcribed. Some original alt texts are only filenames.

## D02 — Chapter 8 The Entity Relationship Data Model

- Figures retained locally with original captions/alt; graphical information not transcribed. Some original alt texts are only filenames.
- Figure 8.1 anchor href points to Attributes image, whereas img src is EntitySet; the rendered img src was collected; original anchor retained in Markdown.

## D03 — Chapter 9 Integrity Rules and Constraints

- Figures retained locally with original captions/alt; graphical information not transcribed. Some original alt texts are only filenames.
- Two original CREATE TABLE textboxes encoded with br tags converted to sql fences; source is Transact-SQL/MS SQL Server, not PostgreSQL. Figure source repeats one image URL; occurrences preserved.

## D04 — Chapter 11 Functional Dependencies

- Figures retained locally with original captions/alt; graphical information not transcribed. Some original alt texts are only filenames.
- Specific attribution cites Creative Commons Attribution-ShareAlike 3.0 for material derived from Wikipedia, in addition to the book-wide CC BY 4.0 notice; both retained.

## D05 — Chapter 12 Normalization

- Figures retained locally with original captions/alt; graphical information not transcribed. Some original alt texts are only filenames.

## D06 — 2.5. Querying a Table

- Preliminary web-tool verification timed out; direct HTTP collection subsequently succeeded with HTTP 200 and full content checks.

## D07 — 2.6. Joins Between Tables


## D08 — 2.7. Aggregate Functions

- One HTML table is a callout explanation, not a data result; preserved as HTML without inventing a header.

## D09 — Chapter 7 The Relational Data Model

- Figures retained locally with original captions/alt; graphical information not transcribed. Some original alt texts are only filenames.

<!-- FIGURE_SUPPLEMENTS_BEGIN -->
## Complementos visuais — triagem e transcrição

Esta etapa mantém intactos os HTML, imagens, Markdown e 31 chunks originais; 69 arquivos do núcleo conferidos com metadata/original_core.sha256. O manifesto inicial e seus indicadores de dependência visual permanecem como registro histórico. A cobertura nova está em metadata/figure_transcriptions.json.

Foram abertas individualmente as 50 imagens originais e avaliadas as 51 ocorrências; a imagem reutilizada de D03 tem dois registros e dois contextos associados. A folha de contato não foi usada como substituto dessa inspeção. Não houve OCR. Ampliações locais serviram apenas à leitura dos pixels existentes, sem declarar resolução recuperada ou revisão humana independente.

| Documento | Ocorrências | Transcritas | Completas | Parciais | Já cobertas no texto | Símbolos explicados |
|---|---:|---:|---:|---:|---:|---:|
| D01 | 3 | 0 | 0 | 0 | 3 | 0 |
| D02 | 15 | 12 | 11 | 1 | 3 | 0 |
| D03 | 17 | 8 | 8 | 0 | 1 | 8 |
| D04 | 7 | 2 | 2 | 0 | 5 | 0 |
| D05 | 4 | 4 | 4 | 0 | 0 | 0 |
| D06 | 0 | 0 | 0 | 0 | 0 | 0 |
| D07 | 0 | 0 | 0 | 0 | 0 | 0 |
| D08 | 0 | 0 | 0 | 0 | 0 | 0 |
| D09 | 5 | 2 | 1 | 1 | 3 | 0 |

Total: **51 ocorrências triadas: 28 selecionadas/transcritas, 15 com função didática já coberta pelo texto e 8 símbolos já explicados**. Nenhuma figura inteira foi classificada como ilegível. Das 28 transcrições, **26 estão completas e 2 têm detalhes incertos explicitamente marcados**. Os valores de telas ilustrativas não essenciais não foram todos transcritos; “já coberta” refere-se à função didática, e essa limitação está registrada por ocorrência.

Foram produzidos **28 novos trechos**, separados em chunks/figure_supplements.jsonl, com IDs Dxx_Fxxx_S001, sem alterar IDs ou texto dos 31 chunks de página. As transcrições se encontram em supplements/figures/. São unidades por figura e podem ter menos de 300 palavras; a faixa 300–600 do corpus original não foi artificialmente imposta a uma fórmula/tabela/diagrama indivisível.

Pendências de legibilidade: D02_F008 (extensão do sublinhado de StartDate na linha JOIN) e D09_F003 (ID, ano e inicial do autor parcialmente encobertos por setas na última linha). Os campos não confirmados estão marcados, sem reconstrução por sequência ou por contexto. Foram tentadas 14 versões maiores no mesmo diretório de uploads, retirando o sufixo de tamanho do nome; todas retornaram HTTP 404. Essas URLs eram candidatas explicitamente identificadas, não fontes substitutas. Respostas e proveniência constam de metadata/figure_resolution_collection.json e supplements/provenance/responses/. Nenhuma imagem nova foi usada nem incorporada ao corpus original.

Quatro observações de divergência da fonte foram separadas em metadata/figure_source_issues.json (endereço na imagem/texto de D01, endpoint N/1 de D02, contradição C → D no texto de D04 e agrupamento de dependências em D04). São pendências para a revisão conceitual posterior; não houve correção silenciosa nem solução de exercícios.

QA dos complementos: cobertura de todas as 51 ocorrências; IDs únicos; vínculos a documentos, imagens e chunks existentes; reutilização de imagem preservada; arquivos e hashes das transcrições; separação de transcrição literal, descrição visual e limites de interpretação; inclusão no inventário e no ZIP. As tabelas de valores foram mantidas na orientação original, incluindo zeros iniciais, casas decimais, células vazias, rótulos repetidos e diferenças de caixa. Esquemas indicam somente chaves e marcas realmente visíveis; mínimos de cardinalidade não foram inventados em diagramas com apenas chave/infinito ou 1/infinito.

Validação de conteúdo: revisão visual por Codex, sem verificação independente por outra pessoa. Esta etapa melhora a recuperação textual das figuras essenciais, mas não transforma as fontes em material conceitualmente corrigido.
<!-- FIGURE_SUPPLEMENTS_END -->
