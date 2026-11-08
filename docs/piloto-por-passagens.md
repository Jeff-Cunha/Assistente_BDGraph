# Extração local por passagens e evidências identificadas

Este documento descreve o piloto inicial, que permitia duas propostas por chamada. A versão atual usa uma proposta e verificação separada; consulte `docs/revisao-piloto-relacao-unica.md` para os novos resultados e comandos. Os dados do primeiro piloto foram preservados.

Foi implementado um piloto que reduz o problema de cópia de citações: o modelo recebe um parágrafo curto e propõe até duas relações, indicando o ID da passagem. O programa valida o ID e copia o parágrafo original, com offsets de início e fim, sem pedir ao modelo que reescreva a evidência.

O corpus não foi alterado. A extração continua dependente do modelo; a fidelidade da citação passa a ser garantida pelo vínculo com o texto original. Isso não garante o sentido correto da relação.

## Implementação

- `scripts/pilot-passage-extraction.py`: cinco passagens selecionadas de D03_C001 e D07_C002; Ollama em localhost, qwen3:8b, contexto 4096, temperature=0, seed=42, think=false, limite de 1024 tokens de saída.
- `tests/test_passage_evidence.py`: quatro verificações de integridade da seleção de evidências.
- `data/extraction/passage-pilot-v1/passages.json`: passagens, IDs e offsets.
- `data/extraction/passage-pilot-v1/*.raw.json`: saídas originais preservadas.
- `data/extraction/passage-pilot-v1/results.json`: tempos e decisões estruturais.
- `data/extraction/passage-pilot-v1/semantic-review.json`: revisão de cada proposta, sem modificar as respostas originais.
- `data/extraction/passage-pilot-v1/extraction-reviewed.json`: somente as duas relações aprovadas na revisão deste piloto, no contrato 0.1.0.

## Resultado observado

| Passagem | Tempo em segundos | Validação estrutural |
|---|---:|---|
| Modelo relacional e restrições | 29,44 | Rejeitada por endpoint não literal |
| Integridade de entidade | 1,88 | Duas propostas válidas estruturalmente |
| Integridade referencial | 1,94 | Duas propostas válidas estruturalmente |
| Registro órfão e junção típica | 1,84 | Duas propostas válidas estruturalmente |
| Left outer join | 1,99 | Rejeitada por endpoint não literal |

Das dez propostas, duas foram aceitas na revisão por Codex, quatro ficaram sinalizadas por problemas semânticos e quatro foram rejeitadas nos grupos que falharam estruturalmente. Não se deve interpretar 2/10 como medida de precisão: as passagens foram selecionadas, o tamanho de amostra é pequeno, há rejeição por grupo e a revisão não foi independente.

Relações preservadas:

- Integridade de entidade → REQUIRES → chave primária. A observação limita a afirmação ao modelo conceitual da fonte, sem afirmar que todo banco físico impede uma tabela sem PK.
- Registro órfão → IS_A → registro. Leitura definicional apoiada no parágrafo original.

O arquivo revisado contém quatro conceitos, duas relações e seis referências a evidências literais. Os nomes portugueses e descrições foram revisados por Codex, separados das citações em inglês. Não é uma extração completa nem substitui o corpus ou a amostra manual anterior.

## Verificações executadas

```powershell
python -m unittest discover -s tests -p test_passage_evidence.py -v
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/passage-pilot-v1/extraction-reviewed.json
```

Os quatro testes passaram e o arquivo revisado passou no validador do contrato. Os testes cobrem preservação de offsets/HTML, rejeição de IDs inexistentes, rejeição de conceitos não mencionados e aceitação de uma lista vazia. Nenhum teste comprova semântica por si só.

## Reproduzir

Com Ollama e qwen3:8b já disponíveis localmente:

```powershell
python scripts/pilot-passage-extraction.py --output data/extraction/passage-pilot-v2 --limit 5
```

Usar novo diretório; não há sobrescrita. A validação atual rejeita todo o grupo quando uma relação contém um endpoint inválido. A revisão é registrada separadamente e não foi automatizada como aprovação por outro modelo.

## Continuidade

O método resolveu a origem literal da citação e reduziu o tempo das consultas curtas após o carregamento. A qualidade semântica ainda não permite processar todo o corpus sem revisão. Próximas opções são limitar cada chamada a uma única relação e incluir verificação específica de direção, modalidade e categoria dos endpoints; comparar com outro modelo local também pode ser útil.

Não expandir estes resultados para todos os documentos, não inserir automaticamente candidatos pending/flagged e não apresentar esta amostra como avaliação independente. As inconsistências de fonte previamente registradas continuam pendentes.
