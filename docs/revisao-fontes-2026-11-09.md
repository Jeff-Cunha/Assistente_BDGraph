> Registro da etapa anterior. Posteriormente o usuário aprovou as modificações; ver data/review/user-approval-source-check-v1.json. As três pendências restantes foram fechadas como remissões contextuais em docs/fechamento-pendencias.md. As observações abaixo descrevem a situação quando esta revisão foi produzida.

# Revisão das fontes após conferência encaminhada pelo usuário

Data: 09/11/2026. Conferência aplicada por Codex diretamente ao corpus. O texto encaminhado está preservado em data/review/source-check-v1/submitted-review.txt; não foi tratado como aprovação humana independente. Este documento registra o resultado aplicado, sem pressupor que a revisão recebida era infalível.

## Resultado

- 26 conceitos existentes tiveram seus resumos/contextos atualizados, em ambos os arquivos quando compartilham o mesmo ID.
- Cinco conceitos foram acrescentados por curadoria manual assistida por IA, em arquivo separado: n-ário, ternário, decomposição de dependências, união de dependências e 2FN.
- As 16 relações existentes, seus IDs e evidências foram preservados sem alteração. Não houve nova geração pelo Ollama.
- A base atual tem 93 conceitos únicos e 16 triplas semânticas únicas. As cinco novas entradas não criam novas relações automaticamente.
- P02, P04, P05, P06 e P07 foram resolvidos nesta revisão de correspondência com as fontes. P01, P03 e P08 permanecem pendentes.

## Resumos revisados

Os identificadores abaixo são os IDs persistidos; os códigos C01–C88 da mensagem do chat eram apenas números de revisão.

| Conceito | Resumo atual | Evidências novas |
|---|---|---|
| C_entity_integrity — integridade de entidade | Regra conceitual segundo a qual toda tabela deve ter chave primária e nenhum componente dessa chave pode ser nulo, conforme a fonte. | D03_C001 |
| C_integrity_constraint — restrição de integridade | Declaração lógica que limita valores e formatos permitidos para os dados; a fonte apresenta integridade de entidade e integridade referencial entre seus tipos. | D03_C001 |
| C_inner_join — junção interna | Junção interna que combina linhas correspondentes e ignora linhas sem correspondência, conforme o exemplo da fonte. | D07_C001, D07_C002 |
| C_left_outer_join — junção externa à esquerda | Junção que preserva cada linha da tabela à esquerda ao menos uma vez; quando não há correspondência à direita, as colunas desse lado recebem valores nulos. | D07_C002 |
| C_normalization — normalização | Ramo da teoria relacional que fornece subsídios ao projeto: caracteriza o nível de redundância e oferece mecanismos de transformação de esquemas para removê-la. | D05_C001 |
| C_third_normal_form — terceira forma normal | Na apresentação didática da fonte, a relação está em 2FN e tem removidas as dependências transitivas: um atributo não chave não pode depender funcionalmente de outro não chave. | D05_C002 |
| C_relational_model — modelo relacional | Modelo introduzido por E. F. Codd em 1970 que descreve o mundo como uma coleção de relações, ou tabelas, inter-relacionadas. | D09_C001 |
| C_primary_key — chave primária | Chave candidata escolhida pelo projetista para identificar unicamente as tuplas de uma tabela; não pode ser nula e é indicada por sublinhado no modelo ER apresentado na fonte. | D02_C004 |
| C_structured_query_language — linguagem de consulta estruturada | Linguagem padrão de acesso a bancos de dados identificada pela sigla SQL, conforme o glossário da fonte. | D09_C003 |
| C_table — tabela | Estrutura que armazena dados em linhas e colunas; D09 também utiliza tabela, relação e arquivo como termos equivalentes no contexto do capítulo. | D09_C001 |
| C_having — cláusula HAVING | Cláusula que seleciona grupos após o agrupamento e a agregação, tipicamente com condições sobre agregados; a fonte ressalva que também pode ser escrita sem funções agregadoras. | D08_C002 |
| C_attribute — atributo | Unidade principal de armazenamento descrita em D09 como coluna, campo ou atributo, que contém componentes básicos dos dados. | D09_C001 |
| C_functional_dependency — dependência funcional | Relação em que, para cada ocorrência válida de X, o valor de X determina unicamente o valor de Y, representada por X → Y. | D04_C001, D05_C002 |
| C_and — operador AND | Operador booleano utilizado em condições de seleção e também em condições de junção nos exemplos da fonte. | D07_C002 |
| C_business_rule — regra de negócio | Regra obtida dos usuários durante o levantamento de requisitos e utilizada para determinar cardinalidade e conectividade. | D03_C003 |
| C_data — dados | Menção contextual aos dados recuperados por SELECT; o trecho utilizado não oferece uma definição geral do conceito de dado. | Evidência anterior mantida; ajuste de escopo |
| C_grouped_row — linha do resultado agrupado | Expressão contextual para uma linha do resultado agrupado, sobre a qual HAVING pode aplicar um filtro. | Evidência anterior mantida; ajuste de escopo |
| C_database_system — sistema de banco de dados | Expressão de categoria utilizada pela fonte para classificar um SGBD relacional; o trecho não apresenta uma definição geral de sistema de banco de dados. | Evidência anterior mantida; ajuste de escopo |
| C_database_administrator — administrador de banco de dados | Administrador de banco de dados, identificado pela sigla DBA; a evidência de glossário apenas expande a sigla. | Evidência anterior mantida; ajuste de escopo |
| C_composite_key — chave composta | Chave formada por dois ou mais atributos e que deve ser mínima, conforme o glossário da fonte. | Evidência anterior mantida; ajuste de escopo |
| C_foreign_key — chave estrangeira | Chave que estabelece uma referência entre tabelas; a fonte a apresenta como atributo que referencia a chave primária de outra tabela e admite a possibilidade de nulo. | Evidência anterior mantida; ajuste de escopo |
| C_non_normalized_table — tabela não normalizada | Tabela caracterizada pela presença de redundância de dados, na terminologia do glossário da fonte. | Evidência anterior mantida; ajuste de escopo |
| C_relation — relação do modelo relacional | Subconjunto de um produto cartesiano de domínios; D09 também o apresenta como termo técnico equivalente a tabela ou arquivo. | D09_C001 |
| C_simple_attribute — atributo simples | Atributo proveniente de um domínio de valores atômicos; D02 também o chama de single-valued attribute. | D02_C003 |
| C_identifying_relationship — relacionamento identificador | Relacionamento em que a PK contém a FK, representado por linha contínua na fonte e também chamado de relacionamento forte. | D02_C005 |
| C_non_identifying_relationship — relacionamento não identificador | Relacionamento em que a FK não integra a PK, representado por linha pontilhada na fonte e também chamado de relacionamento fraco. | D02_C005 |

## Novos conceitos de curadoria manual

| Conceito | Definição com escopo da fonte | Trechos |
|---|---|---|
| C_n_ary_relationship — relacionamento n-ário | No recorte de mapeamento de D02, relacionamento com mais de duas entidades participantes, representado por uma nova relação. | D02_C007 |
| C_ternary_relationship — relacionamento ternário | Relacionamento entre três entidades participantes, representadas por tabelas no exemplo de D02; não se impõe que todos os lados sejam sempre muitos. | D02_C007 |
| C_fd_decomposition — decomposição de dependências funcionais | Regra segundo a qual X → YZ implica X → Y e X → Z; é apresentada como inversa da regra da união. | D04_C003 |
| C_fd_union — união de dependências funcionais | Regra segundo a qual X → Y e X → Z implicam X → YZ. | D04_C002 |
| C_second_normal_form — segunda forma normal | Na apresentação didática de D05, exige 1FN; uma PK simples atende à condição descrita, e, se a PK é composta, cada atributo não chave deve depender de toda a PK, não apenas de parte dela. | D05_C002 |

## Exceções e decisões de projeto

- HAVING: a apresentação enfatiza agregações, mas traz exceção explícita para HAVING sem agregados. O resumo atual preserva as duas informações; não se aceita REQUIRES para afirmar que agregados são sempre obrigatórios.
- FD: normalmente significa functional dependency; a própria legenda da Figura 12.1 em D05_C002 usa excepcionalmente full dependency. Essa ocorrência é uma exceção documentada, não uma segunda equivalência global aplicada automaticamente.
- D09 efetivamente aproxima tabela, relação e arquivo. Manter IDs distintos para tabela e relação é decisão conservadora do projeto; não atribuir essa separação à fonte nem usar D09 para definir arquivo físico.
- D02 efetivamente aproxima atributo simples e monovalorado. A decisão de não fundir é do projeto, e a equivalência da fonte permanece registrada com P03 pendente.
- Relacionamentos forte/identificador e fraco/não identificador ganharam aliases contextuais com evidências de D02.
- Dados, linha do resultado agrupado e sistema de banco de dados são menções contextuais, não definições formais nos trechos selecionados. DBA conserva apenas a expansão da sigla. Os nós não foram apagados, pois alguns são extremos de relações existentes.
- Chave composta, chave estrangeira e tabela não normalizada mantêm as formulações do corpus e suas qualificações. Não foram enriquecidas silenciosamente com conhecimento externo.
- 2FN e 3FN são apresentadas como resumos didáticos da fonte, centrados em PK; não como novas definições formais universais. Na 2FN foram omitidos o se-e-somente-se restritivo e a equivalência indevida entre dependência parcial e aumentação.

## Fontes que exigem cautela

Além dos quatro casos originais de corpus/metadata/figure_source_issues.json, data/review/source-check-v1/source-cautions.json registra a confusão entre aumentação e dependência parcial em D04/D05, o exemplo de reflexividade que requer revisão, a ambiguidade de FD e as equivalências contextuais acima. Os trechos e as figuras originais não foram corrigidos.

O esquema atual não possui um resolvedor automático dessas ressalvas. Quem implementar busca/resolução de nomes deve consultar as notas; encontrar FD em texto não autoriza fundi-lo automaticamente sem considerar a seção.

## Cobertura ainda pendente

BCNF continua fora do recorte inicial. Chave secundária, entidade fraca/forte, dependência de existência, dependências parcial/transitiva, subconsulta, entidade composta/ponte/ligação/JOIN e restrição empresarial/semântica são itens de expansão. Sua presença na fonte não significa que já foram extraídos ou avaliados. Enterprise/semantic constraint não foi fundida automaticamente com semantic rule ou business rule.

## Tabelas para leitura

corpus/reading contém nove cópias para leitura, com seis tabelas de D05 em Markdown e o quadro explicativo de D08 como citação, sem cabeçalho inventado. Client_Interview2 e StaffRoom mantêm cabeçalhos, linhas e valores. Blocos SQL continuam intactos. A advertência inicial e o manifest indicam que essas cópias não devem originar citações, offsets, hashes ou novos chunks. A extração continua usando corpus/processed e corpus/chunks, que não foram alterados.

## Reproduzir e validar

Em uma cópia anterior à aplicação, com os arquivos de destino ainda inexistentes:

```powershell
python scripts/apply-source-review.py --review data/review/source-check-v1/review.json
python scripts/prepare-reading-copies.py
```

O aplicador verifica os hashes dos dois arquivos anteriores, dos chunks, do esquema e da revisão encaminhada, além dos offsets das novas evidências. Ele não sobrescreve saídas existentes. As versões anteriores e suas decisões de revisão permanecem históricas.

```powershell
python -m unittest discover -s tests -p "test_*.py"
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/rule-knowledge-union-v2/extraction.json
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/model-knowledge-union-v3/extraction.json
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/manual-source-review-v1/extraction.json
```

Os 59 testes passaram. As três saídas passaram no validador estrutural e de evidências literais. Essa validação não substitui revisão conceitual humana nem avaliação do sistema de respostas.
