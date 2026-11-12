# Avaliação — GraphRAG/KAG contra RAG vetorial

Rodada feita em 12/11/2026, nesta máquina (Neo4j 5.26.33 local, Ollama 0.40.16, `qwen3:8b`,
GTX 1650 4 GB). Artefatos da rodada: `work/avaliacao/rodada1/` (`resultados.csv` e `resumo.md`).

## 1. Conjunto de perguntas

`data/avaliacao/perguntas.jsonl` — **15 perguntas**, três grupos de cinco:

| Grupo | Quantidade | O que mede |
|---|---|---|
| `conceitual` | 5 | uma pergunta que o corpus responde com um ou dois trechos |
| `multihop` | 5 | pergunta cuja resposta exige dois ou mais relacionamentos do grafo |
| `sem-resposta` | 5 | assunto fora do corpus: o sistema precisa abster-se |

Cada pergunta traz `conceitos` (identificadores do grafo) e `documentos` (documentos de origem).
O gabarito de documentos foi **derivado das evidências das relações do grafo** — o campo
`evidence_chunk_ids` de cada aresta — e não das respostas do sistema. Perguntas multi-hop foram
escolhidas entre caminhos que existem de fato; `tests/test_avaliacao.py` verifica, para cada par
consecutivo da cadeia, que existe uma aresta de um salto no grafo.

## 2. Modos comparados

O mesmo modelo, o mesmo prompt, o mesmo limite de tokens e as mesmas regras de verificação.
Muda **só a recuperação**:

| Modo | Recuperação | Depende de |
|---|---|---|
| `vector` | busca vetorial sobre os 59 trechos, `top_k = 5` | `chunk_embeddings.json` |
| `hybrid` | busca vetorial + travessia do grafo, fusão de ranks, caminho mais curto e centralidade de grau (parte 3) | idem |
| `graph` | plano de consulta Cypher validado executado no Neo4j, com reserva por trecho | Neo4j |

## 3. Critério de acerto

Aplicado igualmente aos três modos, sem julgamento humano do texto:

- **Pergunta com resposta:** `answered = true`, ao menos um documento esperado entre as fontes
  citadas e **nenhuma citação não verificada**.
- **Pergunta sem resposta:** `answered = false` (abstenção).

Nível de sustentação e cobertura são reportados à parte, porque medem outra coisa: o nível olha
quantas fontes distintas a resposta citou, não se a resposta está certa.

Falha de verificação (a resposta do modelo não passa nas regras de fundamentação) conta como
**não acerto** e aparece com o motivo na coluna `observacao`.

## 4. Resultados

45 execuções (15 perguntas × 3 modos), 2 falhas de verificação, 0 citações não verificadas.

| Modo | Corretas | Acerto | Doc. esperado | Abstenção correta | Alto | Médio | Baixo | Insuf. | Tempo médio |
|---|---|---|---|---|---|---|---|---|---|
| `vector` | 9/15 | **60%** | 4/10 | 5/5 | 0 | 4 | 0 | 10 | 65 s |
| `hybrid` | 14/15 | **93%** | 9/10 | 5/5 | 5 | 4 | 0 | 5 | 71 s |
| `graph` | 14/15 | **93%** | 9/10 | 5/5 | 1 | 8 | 0 | 6 | 51 s |

Por grupo de pergunta:

| Grupo | `vector` | `hybrid` | `graph` |
|---|---|---|---|
| conceitual (5) | 3/5 | **5/5** | 4/5 |
| multi-hop (5) | 1/5 | **4/5** | **5/5** |
| sem resposta (5) | 5/5 | 5/5 | 5/5 |

Por pergunta (`acerto / nível / documentos citados`):

| Pergunta | Grupo | `vector` | `hybrid` | `graph` |
|---|---|---|---|---|
| Q01 integridade referencial até junção externa à esquerda | multi-hop | não / insuf. / — | sim / alto / D03,D07 | sim / médio / D07 |
| Q02 integridade de entidade e junção | multi-hop | falha de verificação | sim / alto / D03,D07 | sim / médio / D03 |
| Q03 cláusula WHERE e função MAX | multi-hop | sim / médio / D08 | sim / alto / D06,D08 | sim / médio / D08 |
| Q04 autojunção e junção externa | multi-hop | não / insuf. / — | falha de verificação | sim / médio / D07 |
| Q05 chave primária nas tabelas que a junção combina | multi-hop | não / insuf. / — | sim / alto / D03,D07 | sim / alto / D03,D07 |
| Q06 o que é chave primária | conceitual | sim / médio / D03 | sim / médio / D03 | não / insuf. / — |
| Q07 o que HAVING filtra | conceitual | não / insuf. / — | sim / médio / D08 | sim / médio / D08 |
| Q08 o que é junção interna | conceitual | não / insuf. / — | sim / médio / D07 | sim / médio / D07 |
| Q09 para que serve WHERE | conceitual | sim / médio / D08 | sim / alto / D06,D08 | sim / médio / D08 |
| Q10 AVG/COUNT/SUM/MIN/MAX são o quê | conceitual | sim / médio / D08 | sim / médio / D08 | sim / médio / D08 |
| Q11–Q15 capital da França, Kubernetes, blockchain, bolo, TCP × UDP | sem resposta | 5 abstenções | 5 abstenções | 5 abstenções |

## 5. O que os números dizem

**A diferença está exatamente onde a arquitetura promete.** No grupo multi-hop o baseline
vetorial acerta 1 de 5 e o híbrido 4 de 5. Não é ruído: em Q01, Q04 e Q05 o `vector` recebeu
trechos que falam do assunto e mesmo assim absteve-se, porque o trecho sozinho não responde a
pergunta que exige ligar dois conceitos. É o que o grafo fornece e a busca por similaridade não.

**O `graph` iguala o híbrido e é mais rápido** (51 s contra 71 s), mas produz menos respostas
`high`: 1 contra 5. O plano percorre um caminho e traz as citações daquele caminho; o híbrido
soma evidências de canais diferentes, o que aumenta a chance de citar dois documentos.
Sustentação alta depende de diversidade de fontes citadas, não de velocidade.

**Abstenção é 5/5 nos três modos.** Nenhum dos três respondeu perguntas fora do corpus. No modo
`graph` a recusa acontece antes do modelo: nenhum conceito da pergunta existe no grafo, então o
modelo não é chamado — o que também explica o tempo médio menor.

**Duas falhas de verificação, ambas no mesmo formato:** o modelo devolveu `answered = false`
junto com afirmações citando evidência, e o verificador da parte 4 recusou ("an abstention must
not carry claims"). É o verificador funcionando: a resposta foi barrada em vez de entregue
inconsistente. Como critério, conta como não acerto — e o efeito é maior no híbrido, que perde
justamente a Q04.

**Nenhuma citação não verificada nas 43 respostas.** Todas as citações devolvidas pelo modelo
foram encontradas literalmente nos trechos do corpus.

## 6. Ameaças à validade

- **n = 15.** É uma avaliação de demonstração, não um benchmark. Cada pergunta pesa 6,7 pontos
  percentuais.
- **Uma execução por pergunta e modo.** A mesma pergunta já produziu níveis diferentes em
  execuções repetidas (ver `docs/artigo-parte4.md`), porque o nível depende de quais evidências o
  modelo cita. Repetir três vezes e reportar média reduziria essa variância.
- **Gabarito circular no documento esperado.** Os documentos vêm das evidências das relações do
  grafo; isso favorece `hybrid` e `graph` por construção. O critério não julga se o **texto** da
  resposta está correto, apenas se ela cita o documento certo e se as citações são literais.
- **Um gabarito foi ampliado depois da primeira rodada.** Q09 (WHERE) aceitava apenas D06; o
  `vector` citou D08, que também explica WHERE (5 ocorrências no trecho). A lista passou a
  aceitar D06 **ou** D08, e isso está registrado na nota da pergunta. Sem essa correção, o
  acerto do `vector` seria 8/15 e o dos outros dois 13/15 — a conclusão não muda.
- **Um modelo, uma máquina.** `qwen3:8b` em CPU parcial; outro modelo muda os números, embora as
  citações continuem verificadas pelo mesmo código.

## 7. Como reproduzir

```bash
# banco e modelo no ar (o modo graph precisa do Neo4j)
python scripts/run-avaliacao.py --out work/avaliacao/rodada2
python scripts/run-avaliacao.py --out work/avaliacao/rodada2 --modes vector,hybrid   # sem Neo4j
python scripts/run-avaliacao.py --dry-run --only Q01,Q11                             # sem modelo
python -m pytest -q tests/test_avaliacao.py
```

A rodada é retomável: combinações que já têm `answer.json` são reaproveitadas, então uma
interrupção não perde o que foi medido.
