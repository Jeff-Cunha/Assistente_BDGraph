# Corpus — Assistente de conhecimento sobre bancos de dados com GraphRAG/KAG

Corpus documental da primeira versão acadêmica: fundamentos de bancos de dados, modelagem relacional e SQL básico. Conteúdo original em inglês, sem tradução, resumo, correção editorial ou exemplos sintéticos.

Coleta realizada em **8 de novembro de 2026**. Horários individuais em ISO 8601/UTC no manifesto e nos registros de coleta. As nove fontes solicitadas retornaram HTTP 200, sem redirecionamento dos documentos. PostgreSQL permanece na versão **18**; os HTML coletados identificam a documentação como **18.6**.

Resultado: **9 documentos, 13.377 palavras, 31 trechos sem sobreposição, 50 arquivos de imagem correspondentes a 51 ocorrências**. Os trechos têm entre 301 e 590 palavras. A contagem considera palavras/números no texto renderizado, SQL, resultados e textos alternativos; ignora marcação e destinos de links.

## Estrutura

```text
corpus/
  raw/
    D01.html ... D09.html
    assets/                         imagens originais referenciadas no conteúdo
  processed/
    D01.md ... D09.md
  chunks/
    chunks.jsonl
    figure_supplements.jsonl         complementos visuais separados, 28 novos trechos
  supplements/
    figures/                        28 transcrições/descrições das figuras essenciais
    provenance/responses/           respostas 404 das tentativas de resolução maior
  metadata/
    sources.json                    manifesto dos nove documentos
    collection_log.json             HTTP, tentativas, URL final, hashes e imagens
    quality_checks.json             verificações por documento
    figures.json                    legendas, alt, origem e dependência visual
    figures_contact_sheet.jpg       folha de contato para inspeção
    chunk_size_exceptions.json      vazio nesta coleta
    D01_blocks.json ... D09_blocks.json
    files.sha256                    inventário de integridade da entrega
  licenses/
    D01_notices.html/.txt ... D09_notices.html/.txt
    book.html                       página do livro com declaração geral
    cc_by_4.html
    cc_by_3.html
    cc_by_sa_3.html
    postgresql_18_copyright.html
    postgresql_license.html
    postgresql_18_notice.txt
    collection_log.json
  scripts/
    collect.py
    prepare.py
    inspect_differences.py
    package.py
    requirements.txt
  README.md
  quality_report.md
```

## Fontes e rastreabilidade

| ID | Documento | Origem |
|---|---|---|
| D01 | Fundamental Concepts | Database Design – 2nd Edition, capítulo 2 |
| D02 | The Entity Relationship Data Model | mesmo livro, capítulo 8 |
| D03 | Integrity Rules and Constraints | mesmo livro, capítulo 9 |
| D04 | Functional Dependencies | mesmo livro, capítulo 11 |
| D05 | Normalization | mesmo livro, capítulo 12 |
| D06 | Querying a Table | PostgreSQL 18, seção 2.5 |
| D07 | Joins Between Tables | PostgreSQL 18, seção 2.6 |
| D08 | Aggregate Functions | PostgreSQL 18, seção 2.7 |
| D09 | The Relational Data Model | Database Design – 2nd Edition, capítulo 7 |

Consulte `metadata/sources.json` para URLs solicitadas e finais, autoria/instituição com evidência, edição, licença, avisos específicos, caminhos, horários, hashes e status. `collection_log.json` registra respostas e redirecionamentos de imagens separadamente. Não foram usadas fontes alternativas. O timeout inicial da ferramenta web em D06 foi resolvido pela coleta HTTP direta; isso consta nas observações.

Os arquivos `raw/Dxx.html` contêm os bytes do corpo HTTP recebido, após a descompressão de transporte feita por requests, sem renderização JavaScript, alteração de HTML ou regravação da codificação. Não constituem um espelho navegável do site: CSS, fontes, scripts, páginas vizinhas e arquivos externos não utilizados não foram baixados. As figuras do corpo principal foram coletadas adicionalmente a partir do `img src` original; não foram trocadas silenciosamente pelas imagens apontadas por links ou `srcset`.

## Limpeza e preservação

O extrator usa o elemento `section.chapter` nos capítulos Pressbooks e `#docContent .sect1` no PostgreSQL. Isso exclui menus, sumários do site, cabeçalhos e rodapés de navegação. Autoria do capítulo, notas de rodapé, exercícios originais, bibliografia e atribuições do corpo foram preservados. Apenas âncoras de permalink e marcação sem texto foram removidas.

A hierarquia h1–h6 foi mantida. Títulos semânticos de caixas Pressbooks, como Key Terms e Exercises, que no original são `p.textbox__title`, viraram títulos de nível 2. Um h2 vazio em D03 não produz um título inventado. Parágrafos e listas aninhadas são Markdown; ênfase e negrito usam HTML inline para evitar problemas com pontuação isolada nos originais. As **7 tabelas HTML** são mantidas como HTML dentro do Markdown, preservando células e cabeçalhos existentes sem inventar novos. Dessas, seis estão em D05; a de D08 é uma explicação de chamada, não um resultado tabular.

Os **36 blocos pre** do PostgreSQL foram preservados literalmente quando renderizados, incluindo espaços e linhas dos resultados. Dois exemplos CREATE TABLE de D03, originalmente caixas de texto com br, foram convertidos em blocos SQL. Esses dois exemplos são Transact-SQL/MS SQL Server porque assim aparecem na fonte; não foram adaptados para PostgreSQL. Identificadores, erros de digitação e conteúdo das fontes não foram corrigidos.

Links relativos passaram a URLs absolutas. As imagens usam caminhos relativos ao Markdown em processed: `../raw/assets/...`. O JSONL preserva esses mesmos caminhos; um consumidor deve resolvê-los relativamente ao documento limpo, não ao diretório chunks. Âncoras de links para figuras originais continuam apontando à origem, mesmo quando o href diverge do img src, como na figura 8.1 de D02.

## Figuras e completude

Todas as imagens foram salvas e passaram pela verificação de decodificação. `metadata/figures.json` registra **cada ocorrência**, sua legenda, alt original, dimensões, URL e arquivo local. Em D03, uma imagem é reutilizada: por isso existem 51 ocorrências e 50 arquivos únicos. O figure_id enumera ocorrências e o nome do arquivo enumera downloads únicos; use `local_file` para resolver essa relação.

O texto limpo **não transcreve** relações gráficas, fórmulas ou células existentes somente em imagens. Algumas imagens têm apenas nomes de arquivo no alt. Cada ocorrência foi conservadoramente marcada como dependente de consulta visual; não foi usado OCR nem conteúdo inventado. A folha de contato permite localizar as imagens e observar sua natureza, mas não garante a legibilidade de cada caractere. Para recuperação exclusivamente textual, essas informações visuais continuam sendo uma limitação explícita.

## Divisão em trechos

O algoritmo é determinístico, mantém a ordem e prefere limites de seção/parágrafo. Combina seções curtas adjacentes para alcançar aproximadamente 300–600 palavras. Listas, tabelas, figuras, blocos SQL e seus resultados não são cortados; exemplos são agrupados com o parágrafo que os introduz sempre que possível. O último par de trechos pode ser rebalanceado movendo unidades inteiras. Não há sobreposição.

Cada registro JSONL contém os campos solicitados: `chunk_id`, `document_id`, `section_path`, `chunk_index`, `text`, `source_url`, `language`. Campos adicionais: `section_paths`, `word_count` e `size_note`. `section_path` é uma lista com a ancestralidade comum; quando o trecho atravessa subseções, `section_paths` registra todos os caminhos presentes. Os índices começam em 1. IDs seguem `D01_C001` e se repetem de modo estável para os mesmos snapshots e algoritmo; alterações futuras nas fontes podem deslocar os índices.

A junção de todos os textos dos trechos de cada documento, na ordem e separados por duas quebras de linha, mais a quebra final, reconstrói exatamente seu Markdown. Isso foi verificado para os nove documentos.

## Licenças e atribuições

As declarações consultadas foram preservadas em licenses, assim como os avisos gerais e específicos por documento. O livro declara CC BY 4.0 **com exceções conforme indicado**; D01, D02 e D09 apresentam atribuições de material derivado sob CC BY 3.0. **D04 cita material derivado da Wikipédia sob CC BY-SA 3.0**, além do aviso geral do livro. Esses avisos foram mantidos separadamente, sem reduzir todo o corpus a uma única licença. O PostgreSQL inclui o aviso legal da versão 18, que abrange expressamente documentação, com os créditos ao PostgreSQL Global Development Group e à University of California.

As transformações desta entrega são extração de conteúdo, conversão de formato, resolução de links, armazenamento local de figuras e divisão em trechos. A fonte em inglês foi mantida. Ao transferir ou redistribuir o corpus, mantenha a pasta licenses, as atribuições e os links do manifesto junto aos arquivos.

## Repetir o processo

Ambiente usado: Python 3.13.7. Dependências e versões efetivamente usadas estão em scripts/requirements.txt. Em PowerShell, na pasta deste projeto:

```powershell
python -m venv .venv-corpus
.\.venv-corpus\Scripts\python.exe -m pip install -r corpus\scripts\requirements.txt
.\.venv-corpus\Scripts\python.exe corpus\scripts\collect.py
.\.venv-corpus\Scripts\python.exe corpus\scripts\prepare.py
.\.venv-corpus\Scripts\python.exe corpus\scripts\inspect_differences.py
.\.venv-corpus\Scripts\python.exe corpus\scripts\build_figure_supplements.py
.\.venv-corpus\Scripts\python.exe corpus\scripts\validate_figure_supplements.py
.\.venv-corpus\Scripts\python.exe corpus\scripts\package.py
```

`collect.py` precisa de acesso à internet e sobrescreve os snapshots com a coleta atual; não substitui fontes que falhem. Para reproduzir o processamento **sem rede**, execute apenas prepare.py e package.py sobre estes snapshots. A coleta de novas versões pode mudar números, trechos e avisos; o README descritivo deve então ser atualizado conforme os relatórios gerados. inspect_differences.py não imprime diferenças quando o texto visível está preservado. package.py interrompe a entrega se houver pendências de QA, gera a folha de contato, inventário SHA-256 e `corpus.zip` na pasta que contém corpus.

## Verificação e limites da etapa

`quality_report.md` traz os números por documento e as observações; `metadata/quality_checks.json` contém as verificações detalhadas de títulos, hierarquia, ordem do texto, células, exemplos, resultados, legendas, alt, imagens e cobertura dos trechos. O status com dependência de imagens distingue uma coleta íntegra de uma transcrição integral do conteúdo visual.

Não foram implementados banco de grafos, embeddings, extração de entidades, respostas, interface ou avaliação sintética.

<!-- FIGURE_SUPPLEMENTS_BEGIN -->
## Complementos das figuras — entrega adicional

O núcleo original continua com **9 documentos, 31 chunks e 13.377 palavras**, sem alteração. A etapa visual acrescenta **28 transcrições/descrições e 28 trechos separados**; são 5020 palavras nesses trechos, contadas pelo mesmo método de renderização. As contagens originais não incluem os complementos.

- `supplements/figures/Dxx_Fxxx.md`: um complemento por figura selecionada, com IDs próprios e proveniência. O texto em inglês separa rótulos/valores literais, descrição das marcas visuais e limites de interpretação. Colchetes descrevem símbolos ou incertezas editoriais e não simulam texto da imagem.
- `chunks/figure_supplements.jsonl`: novos registros com `content_type=figure_transcription`, `figure_ids`, `parent_chunk_ids`, imagens originais e caminho da transcrição. **Carregue este arquivo além de chunks/chunks.jsonl**, preservando o tipo e a proveniência. Um suplemento não é uma citação literal do corpo da página.
- `metadata/figure_transcriptions.json`: um registro para cada uma das 51 ocorrências, com triagem, justificativa, método, revisão visual, status, arquivo e pendências. Quinze ilustrações têm a função didática já coberta; oito símbolos já estão explicados no texto. A classificação não promete a transcrição de cada valor de telas não essenciais.
- `metadata/figure_supplement_quality.json`: contagens e QA; `metadata/figure_source_issues.json`: divergências das fontes deixadas para revisão conceitual.
- `metadata/original_core.sha256`: baseline dos 69 arquivos originais preservados; `metadata/files.sha256`: inventário da entrega atual inteira.
- `scripts/figure_annotations.json`: anotações visuais curadas, fonte dos novos arquivos. `scripts/build_figure_supplements.py`: geração determinística dos complementos, associações e seção adicional dos relatórios. Não realiza uma nova revisão visual ao ser executado.
- `metadata/figure_resolution_collection.json` e `supplements/provenance/responses/`: evidências das 14 tentativas de imagens maiores, todas HTTP 404. Respostas HTML de erro são apenas evidência de coleta, não imagens nem texto para recuperação.

**26 transcrições completas e 2 parciais**: a extensão do sublinhado de StartDate em D02_F008 e caracteres sob setas em D09_F003 não puderam ser confirmados. Não foi preciso marcar nenhuma imagem inteira como ilegível. A ampliação de pixels não foi tratada como aumento de resolução. Não houve OCR nem revisão humana independente. As atribuições/licenças das fontes continuam em licenses e são referenciadas por cada complemento; não se presumiu uma licença única para todo o material.

Para reconstruir a entrega sobre estes snapshots, execute `python corpus/scripts/build_figure_supplements.py` depois de prepare.py (se este for reexecutado) e **antes de package.py**. O builder repõe suas seções adicionais em README/quality_report sem duplicá-las. A coleta original não precisa ser reexecutada. `python corpus/scripts/validate_figure_supplements.py` confere o núcleo e os complementos; package.py também exige essa validação quando houver complementos. As tentativas de maior resolução podem ser repetidas com fetch_figure_originals.py, mas não são necessárias para reproduzir as transcrições já revisadas.
<!-- FIGURE_SUPPLEMENTS_END -->
