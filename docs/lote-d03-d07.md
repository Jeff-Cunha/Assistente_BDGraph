# Lote de extração e revisão de D03 e D07

Foram processadas as passagens elegíveis dos oito trechos de página de D03 (integridade e restrições) e D07 (JOIN), com Qwen3 8B local, uma relação por chamada e verificação separada pelo mesmo modelo. O processamento não equivale a cobertura completa dos conceitos: usa parágrafos de pelo menos 15 palavras, exclui algumas estruturas e não inclui os suplementos de figuras.

## Execução

| Trecho | Passagens processadas |
|---|---:|
| D03_C001 | 8 |
| D03_C002 | 5 |
| D03_C003 | 4 |
| D03_C004 | 18 |
| D03_C005 | 15 |
| D03_C006 | 11 |
| D07_C001 | 8 |
| D07_C002 | 6 |

Total: 75 passagens reais e 2 controles negativos sintéticos, armazenados separadamente e proibidos na exportação para o grafo. A soma dos tempos registrados de inferência foi 224,49 segundos; esse número não inclui todo o trabalho de revisão nem todo overhead.

Resultado da triagem das 77 entradas: 13 propostas passaram para revisão, 62 foram rejeitadas e 2 entradas produziram abstenção. Um controle foi rejeitado e o outro teve abstenção. Portanto, a triagem do extrator e a ausência de relações na saída final não são a mesma coisa.

## Revisão e saída

As 13 propostas que passaram foram conferidas por Codex contra as evidências. Três foram aprovadas; dez ficaram sinalizadas, por exemplo por representar valores e nomes de tabelas de exemplo como conceitos gerais, confundir sinônimos com tipos ou perder condições da afirmação. As recusas anteriores foram preservadas, mas não todas reavaliadas conceitualmente; pode haver falsos negativos.

Relações mantidas:

1. entity integrity → REQUIRES → primary key, no escopo conceitual da fonte.
2. relational database management system → IS_A → database system.
3. join → COMBINES → row, com evidência original na forma plural rows.

O JSON revisado contém seis conceitos, três relações e nove referências literais. As citações em inglês vieram do corpus por ID e offsets; as traduções, os nomes canônicos e as descrições foram curados por Codex. Não houve revisão humana independente. A aprovação é da correspondência com as fontes no escopo descrito, sem certificação universal da verdade do material.

O volume aproveitável é pequeno e insuficiente para representar toda a matéria. Não se deve calcular precisão/recall a partir dessas contagens, pois não existe anotação independente e completa dos fatos esperados. O extrator e seu autoverificador ainda demonstram baixa cobertura e falhas semânticas; os demais documentos não foram processados neste lote.

## Arquivos

- `data/extraction/d03-d07-batch-v1/passages.json`: unidades de entrada e posições no texto.
- `coverage.json`: política de seleção e cobertura de caracteres por trecho.
- `instruction.txt` e `run-config.json`: instrução, parâmetros, versão por hash e digest do modelo.
- `*.raw.json`: respostas originais do gerador e do verificador.
- `results.json`: decisões estruturais, verificações, tempos e propostas.
- `review-decisions.json`: decisão para cada entrada e definições canônicas; as aprovações identificam origem, destino e predicado esperado. O hash do lote vincula a revisão à entrada revisada.
- `extraction-reviewed.json`: somente o conhecimento aprovado desta rodada, no contrato 0.1.0.

Nenhum arquivo anterior foi sobrescrito. O método da saída é llm_candidates, com revisão posterior identificada; não é a amostra manual inicial. A relação de integridade de entidade reutiliza R_sample_002, pois corresponde à tripla já conhecida. Ao ingerir junto à amostra inicial, reunir evidências, não duplicar essa aresta.

## Reprodução e verificação

Com Ollama local e modelo instalado, executar em diretório novo:

```powershell
python scripts/pilot-passage-extraction.py --documents D03 D07 --output data/extraction/d03-d07-batch-v2 --semantic-check --negative-controls
```

O script agora tem modo de lote por documentos. A opção --limit só controla a seleção curta do piloto; não limita o modo --documents. Os suplementos de figuras continuam fora deste comando, explicitamente.

Depois de conferir e registrar as decisões, exportar para um arquivo novo:

```powershell
python scripts/export-passage-review.py --batch data/extraction/d03-d07-batch-v1/results.json --review data/extraction/d03-d07-batch-v1/review-decisions.json --output data/extraction/d03-d07-batch-v1/extraction-reviewed-v2.json
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/d03-d07-batch-v1/extraction-reviewed-v2.json
```

O exportador exige decisão para todas as entradas, bloqueia controles sintéticos, verifica os offsets, preserva IDs de relações existentes e impede mudança silenciosa do predicado após a revisão. As evidências recusadas não são reescritas para tentar passar.

Foram executados 27 testes, todos aprovados, e o arquivo revisado passou na validação estrutural com seis conceitos, três relações e nove evidências. Esses testes não substituem avaliação conceitual.

## Continuidade

Este lote permite testar uma saída realmente proposta pelo modelo e revisada, mas não conclui a parte 1. Antes de ampliar para o restante do corpus, é necessário melhorar cobertura e qualidade semântica, revisar o vocabulário de predicados e comparar uma estratégia/modelo alternativo. A amostra manual inicial continua válida para a pessoa 2 desenvolver a ingestão.
