# Seção do artigo — Avaliação, integração e comparação com RAG vetorial

> Parte 6 do projeto GraphRAG/KAG sobre bancos de dados e SQL.
> Números medidos nesta máquina (Neo4j 5.26.33, Ollama 0.40.16, `qwen3:8b`, GTX 1650 4 GB),
> em 12/11/2026. Artefatos em `work/avaliacao/rodada1/`; método completo em
> [avaliacao.md](avaliacao.md).

## 1. Papel desta etapa no sistema

A etapa 6 responde a pergunta que o restante do trabalho só pode sugerir: **o grafo ajuda de
fato?** Ela define o conjunto de perguntas, executa os modos de recuperação com o mesmo modelo e
as mesmas regras, mede o resultado e integra as cinco etapas anteriores em um estado executável
(o `main` com as partes 1 a 5 mergeadas, 199 testes automatizados).

## 2. Problema

Sem avaliação, um sistema desse tipo só tem arquitetura. Três dificuldades apareceram:

1. **Comparar sem julgar texto.** Não há gabarito humano frase por frase, e inventar um seria
   pior que medir outra coisa. A saída foi escolher critérios mecânicos: documento de origem
   citado, citação verificada literalmente, abstenção onde não há resposta.
2. **Gabarito que não nasce da resposta.** Se o documento esperado fosse extraído das respostas
   do próprio sistema, a avaliação seria circular. Ele vem das evidências das relações do grafo.
3. **Perguntas multi-hop que existem.** Com 23 relações semânticas, uma pergunta multi-hop
   escolhida ao acaso provavelmente não tem caminho. As perguntas foram selecionadas a partir dos
   caminhos reais e há um teste que verifica cada aresta da cadeia.

## 3. Método

**15 perguntas** em três grupos de cinco: conceituais, multi-hop e sem resposta no corpus.
**Três modos** com o mesmo modelo, prompt, orçamento de tokens e verificador — muda só a
recuperação: `vector` (só busca vetorial), `hybrid` (vetor + grafo, RRF, caminho mais curto,
centralidade de grau) e `graph` (plano Cypher validado no Neo4j).

**Critério de acerto**, idêntico nos três modos:

| Grupo | Acerto |
|---|---|
| com resposta | `answered`, ao menos um documento esperado citado, zero citação não verificada |
| sem resposta | abstenção |

Uma **falha de verificação** (a resposta do modelo é recusada pelas regras de fundamentação)
conta como não acerto, com o motivo registrado.

## 4. Implementação

| Arquivo | Papel |
|---|---|
| `data/avaliacao/perguntas.jsonl` | as 15 perguntas com gabarito de conceitos e documentos |
| `scripts/run-avaliacao.py` | executa os modos, mede e gera `resultados.csv` e `resumo.md`; retomável |
| `tests/test_avaliacao.py` | 11 testes: gabarito válido contra grafo e corpus, critério de acerto, resumo |
| `app/engine.py` | `answer_from_evidence()` separa a etapa "perguntar ao modelo" da recuperação |

A separação em `answer_from_evidence()` é o que torna a comparação justa: o baseline vetorial
monta um pacote de evidências no mesmo formato do contrato e passa pelo **mesmo** caminho de
prompt, verificação e cálculo de sustentação.

## 5. Resultados

45 execuções, 2 falhas de verificação, 0 citações não verificadas.

| Modo | Corretas | Acerto | Doc. esperado | Abstenção correta | Nível alto | Tempo médio |
|---|---|---|---|---|---|---|
| `vector` | 9/15 | 60% | 4/10 | 5/5 | 0 | 65 s |
| `hybrid` | 14/15 | 93% | 9/10 | 5/5 | 5 | 71 s |
| `graph` | 14/15 | 93% | 9/10 | 5/5 | 1 | 51 s |

Por grupo:

| Grupo | `vector` | `hybrid` | `graph` |
|---|---|---|---|
| conceitual | 3/5 | 5/5 | 4/5 |
| multi-hop | 1/5 | 4/5 | 5/5 |
| sem resposta | 5/5 | 5/5 | 5/5 |

**A diferença aparece onde a arquitetura promete.** No grupo multi-hop o baseline vetorial acerta
1 de 5. Em Q01, Q04 e Q05 ele recebeu trechos sobre o assunto e ainda assim absteve-se: o trecho
isolado não responde a uma pergunta que exige ligar dois conceitos. É exatamente o que a
travessia do grafo acrescenta.

**`graph` troca diversidade por velocidade.** Iguala o acerto do híbrido em 93%, responde 20 s
mais rápido e recusa perguntas fora do grafo sem chamar o modelo — mas produz uma única resposta
`high`, contra cinco do híbrido, porque um caminho tende a citar um documento só.

**Abstenção 5/5 nos três modos.** Nenhum modo respondeu pergunta fora do corpus — o ponto que
motiva o projeto.

**Falhas de verificação como resultado, não como ruído.** Em Q02 (`vector`) e Q04 (`hybrid`) o
modelo devolveu `answered = false` acompanhado de afirmações com evidência, e o verificador da
parte 4 recusou. A resposta foi barrada em vez de entregue inconsistente; para o critério, conta
como não acerto.

## 6. Ameaças à validade

- **n = 15 e uma execução por célula.** Cada pergunta vale 6,7 pontos percentuais, e o nível de
  sustentação já variou entre execuções repetidas da mesma pergunta. Repetir e reportar média
  reduziria a variância; três execuções custariam ~3,5 h de GPU.
- **Circularidade parcial.** O documento esperado vem das evidências do grafo, o que favorece
  `hybrid` e `graph` por construção. O critério não julga a correção do texto, só a fonte e a
  literalidade das citações.
- **Uma correção de gabarito declarada.** Q09 passou a aceitar D06 **ou** D08 depois da primeira
  rodada, porque D08 também explica WHERE. Sem a correção: `vector` 8/15 e os outros 13/15 — a
  conclusão não muda.
- **Falha de verificação não é erro de recuperação.** As duas falhas vêm do formato da resposta
  do modelo, e por isso pesam mais no modo com mais evidências (híbrido).
- **Um modelo, uma máquina.** Outro modelo muda os números; a verificação das citações, não.

## 7. Limitações e continuidade

- Ampliar a extração de relações (23 hoje) é o que mais aumentaria a cobertura multi-hop: as
  perguntas de avaliação existentes já usam praticamente todos os caminhos disponíveis.
- Repetir a rodada três vezes, com intervalo, e reportar média e dispersão por pergunta.
- Incluir as 5 perguntas sem resposta com variações paráfrase para testar robustez da abstenção.
- A integração das partes 1–5 está no `main` com 199 testes; o conjunto de avaliação é o artefato
  que a etapa de consolidação do artigo deve citar como resultado empírico.
