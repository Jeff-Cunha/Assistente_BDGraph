# Seção do artigo — Integração com LLM, geração segura de Cypher e respostas fundamentadas

> **Rascunho de trabalho da parte 4.** Números marcados como *medido* foram obtidos neste
> repositório; trechos marcados como **PENDENTE** dependem da execução com o modelo e o banco
> reais e não devem ser preenchidos por estimativa. Revisar voz e formato com os responsáveis
> pela consolidação do artigo antes de submeter.

## 1. Papel desta etapa no sistema

O sistema em construção responde perguntas sobre bancos de dados a partir de um corpus de nove
documentos, usando um grafo de conhecimento em Neo4j e um modelo de linguagem local. A etapa aqui
descrita recebe da recuperação um conjunto de trechos de evidência e caminhos do grafo e devolve
uma resposta em português com citações rastreáveis, a consulta Cypher executada e um indicador de
sustentação documental.

A contribuição não está em "usar um LLM", mas em **restringir o que o modelo pode fazer e
verificar o que ele afirmou**. Duas decisões organizam o restante desta seção:

1. o modelo de linguagem não escreve Cypher livre por padrão — ele escolhe um plano de consulta
   em um vocabulário fechado, que o sistema compila;
2. o modelo não informa confiança — ele apenas declara afirmações e as evidências que usou, e o
   nível de sustentação é derivado por regras sobre essas citações.

## 2. Problema

Três riscos motivam essas decisões.

**Risco operacional.** Cypher é uma linguagem completa, com cláusulas de escrita (`CREATE`,
`MERGE`, `SET`, `DELETE`), controle transacional, importação de arquivos (`LOAD CSV`) e chamada
de procedimentos de extensão (`apoc`, `gds`). Um texto gerado por modelo pode conter qualquer um
desses construtos, inclusive por engano. Em um banco que outras etapas também populam, uma
consulta destrutiva compromete o trabalho de toda a equipe.

**Risco de exposição.** Mesmo uma consulta de leitura pode devolver mais do que o necessário.
Devolver o nó inteiro (`RETURN n`) expõe todos os campos gravados, entre eles os vetores de
*embedding* que a etapa de recuperação grava nos trechos — dados volumosos e sem relação com a
pergunta. Do mesmo modo, `MATCH (n)` sem rótulo varre todos os rótulos existentes, e não apenas
os três do contrato.

**Risco de alucinação.** Um modelo pode citar uma fonte que não existe, exagerar a modalidade de
uma afirmação ("tipicamente" virar "sempre") ou simplesmente responder de memória. A instrução do
*corpus* do projeto já proíbe tratar probabilidade gerada pelo modelo como confiança calibrada;
o mesmo princípio se aplica aqui.

## 3. Método

### 3.1 Geração por plano, não por texto

O modelo recebe a pergunta e devolve um objeto JSON com nó inicial, até quatro saltos (direção e
tipos de relação) e um limite de linhas. Todos esses valores vêm de listas fechadas: três rótulos
(`Document`, `Chunk`, `Concept`), dezessete tipos de relação (três estruturais, oito semânticos
iniciais e seis introduzidos pela cobertura SQL) e identificadores com formato fixo
(`C_...`, `D03_C001`, `D01`).

O sistema compila esse plano em **uma** consulta de caminho determinística, com todos os valores
como parâmetros. Como consequência, o texto da consulta não depende da redação do modelo: a mesma
pergunta, com o mesmo plano, produz exatamente a mesma consulta, o que torna o registro
auditável e comparável entre execuções.

### 3.2 Validação de Cypher livre como alternativa

Para casos em que o plano não expressa a intenção, existe o caminho de Cypher livre, aceito apenas
se passar por todas as verificações do Quadro 1. O verificador opera sobre uma sequência de
tokens, não sobre expressões regulares sobre o texto: comentários, literais de texto,
identificadores entre crases, rótulos, tipos de relação e acessos a propriedade são examinados em
contexto.

**Quadro 1 — Regras aplicadas ao Cypher livre.**

| Regra | Motivo |
|---|---|
| Uma única instrução; `;` recusado | impede encadear comandos |
| Nenhum comentário, nenhum identificador entre crases | elimina conteúdo não interpretado |
| Nenhuma string literal; valores só como `$parâmetro` | o texto do modelo nunca vira sintaxe |
| Cláusulas de escrita, transação, importação e `SHOW` recusadas | leitura somente |
| `CALL`, `apoc`, `gds`, `dbms` recusados | nenhum procedimento de extensão |
| Rótulos, tipos e propriedades apenas os do contrato | o modelo não alcança outro dado |
| Todo padrão de nó precisa de rótulo | impede varredura de todos os rótulos |
| `RETURN n` e `RETURN *` recusados | impedem ler todos os campos, inclusive vetores |
| Toda relação precisa declarar tipo | evita travessia genérica |
| `*` só com limite superior explícito e dentro do orçamento | impede explosão combinatória |
| `LIMIT` obrigatório, injetado como `$limit` quando ausente | protege o banco |
| Parâmetros fornecidos precisam cobrir a consulta | falha explícita, sem omissão silenciosa |

A execução acrescenta uma segunda barreira independente do texto: toda consulta roda com
`execute_query(..., routing_=READ)`. A edição Community do Neo4j não oferece controle de acesso
por papel, e o próprio servidor recusa escrita em modo leitura com
`Neo.ClientError.Statement.AccessMode`. A verificação textual e o modo de acesso são, portanto,
proteções complementares, não alternativas: a primeira impede que a consulta chegue ao banco, a
segunda protege caso a primeira seja contornada.

### 3.3 Respostas fundamentadas

O modelo recebe a pergunta, os trechos de evidência e os nomes dos conceitos, cada evidência
identificada por um rótulo curto (`E1`, `E2`, ...). **Nenhuma URL é enviada ao modelo**: o
sistema resolve os identificadores em endereço, documento e seção depois. Assim, o modelo não tem
o que inventar ao citar.

A resposta é exigida em um objeto JSON com quatro campos: se respondeu, o texto em português, uma
lista de afirmações e, para cada afirmação, os identificadores de evidência. A verificação
posterior é determinística:

- identificador de evidência fora do pacote recebido → **resposta recusada** e a resposta bruta
  preservada para inspeção;
- campo fora do esquema (por exemplo, `confidence`) → recusada;
- afirmação sem nenhuma evidência → descartada e listada separadamente; se sobrar nenhuma, a
  resposta vira abstenção;
- texto de recusa do modelo → substituído por uma frase fixa do sistema, com o motivo registrado.

Nada é corrigido em silêncio. Além disso, cada citação é conferida como substring literal do
trecho armazenado no corpus; o que não coincide é sinalizado ao usuário.

### 3.4 Indicador de sustentação

O nível não vem do modelo. Ele é derivado das citações efetivamente usadas, conforme o Quadro 2,
e acompanhado de uma lista de motivos em português.

**Quadro 2 — Níveis de sustentação.**

| Nível | Critério |
|---|---|
| `insufficient` | nenhuma afirmação sobreviveu à verificação |
| `low` | há evidência pendente ou sinalizada na revisão, ou houve afirmação descartada |
| `medium` | citações aceitas, mas de um único trecho, de um único documento, ou citação não conferida |
| `high` | citações aceitas, de ao menos dois trechos e de ao menos dois documentos |

O indicador descreve **sustentação documental**, não probabilidade de acerto — distinção que o
contrato de integração do projeto exige explicitamente. Um valor `high` significa que a resposta
se apoia em fontes distintas e aceitas, não que esteja correta.

## 4. Implementação

O código usa apenas a biblioteca padrão de Python, com uma exceção: o driver oficial do Neo4j,
importado dentro das funções, de modo que as demais verificações funcionem sem ele. A escolha
mantém o custo de reprodução baixo e evita dependências que a banca não possa instalar.

| Arquivo | Função |
|---|---|
| `scripts/guard-cypher.py` | compilação do plano e validação do Cypher livre |
| `scripts/neo4j-executor.py` | execução em modo leitura e conversão dos caminhos em evidências |
| `scripts/answer-grounding.py` | verificação da resposta, resolução das citações e nível |
| `scripts/run-answer-ollama.py` | adaptador do modelo local, com manifesto por execução |
| `schemas/answer.schema.json` | contrato de saída consumido pela interface |
| `data/llm/testes/cypher-ataques.jsonl` | conjunto de tentativas de contorno |

Cada execução grava um manifesto com modelo, *digest*, parâmetros de decodificação, hashes do
pacote de evidências e do *prompt*, tempos e contagem de tokens, além da resposta bruta. A
decodificação usa temperatura zero e semente fixa; o projeto registra que isso reduz, mas não
garante, reprodutibilidade entre versões de *runtime* e hardware.

## 5. Resultados obtidos até aqui

Os números abaixo são medidas do repositório, não estimativas.

**Verificador de Cypher.** O conjunto de ataques tem 38 casos: 32 recusas obrigatórias, 5
controles e 1 caso aceito de propósito como limite conhecido. Todas as 32 recusas usam a mensagem
da regra correspondente e todos os 5 controles são aceitos. Uma verificação independente do campo
"esperado" confirma que nenhum caso contendo escrita, procedimento, `embedding`, `.password` ou
`RETURN *` é aceito.

**Suíte de testes.** A parte 4 contribui com 90 testes automatizados em 155 do repositório, sem
necessidade de banco, de modelo ou de rede: 26 do verificador, 4 do conjunto de ataques, 15 do
executor, 21 da fundamentação, 19 do adaptador e 5 dos planos de exemplo.

**Dados disponíveis.** O grafo carregado pela etapa de modelagem tem 9 documentos, 59 trechos, 93
conceitos e 23 relações semânticas; a ingestão foi executada contra Neo4j 5.26.33 local, com 23
de 23 triplas, 134 `MENTIONS`, 3 restrições de unicidade e todos os índices `ONLINE`.

**Execução com o modelo (uma pergunta, duas execuções).** Com `qwen3:8b` no Ollama 0.40.16 local,
a pergunta do exemplo foi respondida nas duas vezes em que rodou, com resultados diferentes:

| Execução | Tempo | Tokens de saída | Nível | Afirmações | Documentos citados |
|---|---|---|---|---|---|
| 1 | 92,3 s | 256 | `high` | 3 | D03, D07 |
| 2 | 99,6 s | 214 | `medium` | 2 | D03 |

A consulta compilada e o caminho recuperado foram **idênticos** nas duas execuções — uma aresta
de cada tipo, um único caminho. O que mudou foi quais evidências o modelo citou: na primeira ele
usou também a citação de D07, na segunda ficou em D03. Como o nível é calculado sobre as citações
verificadas, e não sobre o que foi recuperado, a mesma pergunta pode oscilar entre `high` e
`medium`. Isso é uma propriedade do indicador, não um defeito: ele mede a resposta entregue.
Distribuição de aceitas, recusadas e abstenções exige o conjunto de avaliação da parte 6.

**Execução contra o banco.** O caminho completo foi exercitado contra Neo4j 5.26.33 real: plano
compilado, execução em modo leitura, evidências por aresta e resposta verificada. O orçamento de
saltos é um único número (`DEFAULT_MAX_HOPS = 4`) no guard, no executor e nos adaptadores, e
`tests/test_plan_examples.py` garante que nenhum exemplo do repositório exija mais do que isso.

**PENDENTE — comparação GraphRAG versus RAG vetorial.** Compete à etapa de avaliação; esta seção
fornece o formato de saída (resposta, citações, nível) necessário para a comparação.

## 6. Ameaças à validade

**Validade de construto.** O nível de sustentação mede cobertura e diversidade de fontes, não
verdade. Uma resposta pode ser `high` e ainda estar errada se as próprias relações do grafo
estiverem erradas; a cadeia de revisão da extração é o que sustenta essa premissa, e ela não teve
revisão humana independente até o momento.

**Validade interna.** O conjunto de ataques foi escrito pela mesma pessoa que escreveu o
verificador, o que favorece o resultado. Os controles e a verificação independente do campo
"esperado" reduzem, mas não eliminam, esse viés. Um caso é aceito deliberadamente (alargamento
semântico com parâmetro), o que documenta o limite em vez de escondê-lo.

**Validade externa.** O vocabulário fechado vale para este grafo. Em outro domínio, as listas de
rótulos, tipos e propriedades mudam, e o verificador precisa ser reconfigurado — o que é
justamente o que se espera de uma proteção por contrato.

**Amostra de duas execuções.** Há uma pergunta executada de ponta a ponta, duas vezes, não uma
avaliação. Duas respostas não sustentam afirmação sobre taxa de alucinação nem sobre tempo médio.
A variação de nível entre as duas execuções, com o mesmo caminho recuperado, mostra também que o
indicador depende do comportamento do modelo ao citar — o que reforça a necessidade do conjunto de
avaliação da parte 6.

## 7. Limitações e continuidade

- O verificador não é um analisador sintático completo de Cypher; a proteção depende também do
  modo de acesso do servidor. As duas barreiras precisam ser mantidas.
- A decisão de exigir tipo explícito em toda relação e rótulo em todo padrão de nó reduz a
  expressividade em troca de previsibilidade; consultas legítimas que precisem de travessia
  genérica deixam de ser aceitas.
- O modelo local `qwen3:8b` já apresentou, na etapa de extração do projeto, dificuldade em citar
  literalmente e em preservar modalidade. Nada indica que responder seja mais fácil; por isso a
  verificação é posterior e obrigatória, e não uma recomendação.
- A integração com a interface está prevista pelo contrato `schemas/answer.schema.json`, que já
  inclui citações por afirmação, fontes agrupadas, motivos do nível e limitações declaradas.

## 8. O que esta seção entrega ao artigo final

1. A descrição das duas barreiras independentes contra escrita e exposição de dados.
2. O conjunto de 38 casos de contorno como instrumento de avaliação reproduzível.
3. A regra determinística de sustentação, com critérios auditáveis e vocabulário de motivos.
4. A distinção explícita entre sustentação documental e probabilidade de acerto.
5. Uma lista de lacunas declaradas, para que a discussão de resultados não precise ser
   reinterpretada depois.
