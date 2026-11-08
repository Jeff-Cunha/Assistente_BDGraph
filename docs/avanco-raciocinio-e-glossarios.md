# Extração local com comparação de raciocínio e glossários

Esta rodada comparou o modo de raciocínio do Qwen3 8B, repetiu o piloto por passagens e adicionou um extrator por regras para definições que as próprias fontes apresentam em seus glossários. Corpus, citações e saídas anteriores foram preservados.

## Comparação de desenvolvimento

Quatro casos foram rotulados por Codex: requisito condicional inadequado, classificação de self join como join, direção invertida dessa classificação e suporte explícito a restrições pelo modelo relacional. Os rótulos esperados não foram enviados ao modelo.

| Modo | Correspondência com os quatro rótulos | Soma dos tempos das chamadas |
|---|---:|---:|
| Sem raciocínio | 2 de 4 | 17,45 s |
| Com raciocínio | 4 de 4 | 47,51 s |

Esses são casos escolhidos para desenvolvimento, não um teste independente ou representativo. Não demonstram acurácia geral. A comparação completa está em data/extraction/reasoning-comparison-v1/comparison.json. O script scripts/compare-local-reasoning.py reproduz o experimento.

## Novo piloto com raciocínio

Foram executadas sete passagens reais e dois controles sintéticos, com think=true no gerador e no verificador, contexto 8192 e orçamento de 4096 tokens por chamada. Também foi explicitado que nomes de conceitos devem manter a forma literal, inclusive plurais. Portanto, não é uma comparação controlada apenas do parâmetro think com o piloto anterior.

Resultado: quatro propostas passaram para revisão, três entradas foram rejeitadas e os dois controles produziram abstenção. Das quatro propostas que passaram, Codex manteve três e sinalizou uma: referential integrity REQUIRES no orphan records usa uma proposição negativa como se fosse um conceito simples e não foi exportada.

Relações mantidas após revisão:

- relational model → SUPPORTS → constraints.
- entity integrity → REQUIRES → primary key, no escopo conceitual da fonte.
- self join → IS_A → join.

Houve uma resposta vazia e outra truncada, ambas recusadas. A soma das chamadas foi 251,77 s, significativamente maior que a rodada curta sem raciocínio. Não se deve habilitar esse modo para todo o corpus presumindo que resolverá as falhas ou manterá a velocidade anterior.

As saídas originais estão em data/extraction/passage-reasoning-v1; review-decisions.json registra a revisão por Codex, sem revisão humana independente. extraction-reviewed.json contém somente as três relações mantidas.

## União revisada para integração

O arquivo data/extraction/reviewed-union-v1/extraction.json reúne apenas as duas saídas derivadas do modelo e revisadas: o lote D03/D07 anterior e este novo piloto. A amostra manual inicial não foi copiada para essa união.

Resultado: **9 conceitos, 5 relações e 15 referências literais**, sem duplicação da relação de integridade de entidade. O manifesto registra hashes das entradas. Os IDs já existentes foram preservados. O arquivo passou no validador do contrato 0.1.0.

Para reproduzir em arquivo novo:

```powershell
python scripts/merge-reviewed-extractions.py --inputs data/extraction/d03-d07-batch-v1/extraction-reviewed.json data/extraction/passage-reasoning-v1/extraction-reviewed.json --output data/extraction/reviewed-union-v2/extraction.json
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/reviewed-union-v2/extraction.json
```

Conceitos pending/flagged não podem entrar nesse comando. Conflitos de ID ou de identidade canônica exigem resolução; não são fundidos silenciosamente. Quando descrições curadas diferem, a primeira é mantida e os arquivos de origem continuam disponíveis. Ao usar essa saída junto à amostra manual no Neo4j, reunir evidências por IDs/triplas e não criar arestas paralelas para a mesma relação.

## Definições extraídas dos glossários

scripts/extract-glossary-concepts.py identificou **72 definições, agrupadas em 71 nomes**, nas seções Key Terms de seis documentos: D01, D02, D03, D04, D05 e D09. Os demais documentos não possuem essa estrutura e não são cobertos por essa regra.

As definições são cópias do texto original, não explicações geradas. Cada entrada preserva documento, trecho, offsets, citação integral e URL. Siglas entre parênteses podem ajudar a mapear IDs conhecidos, mas nenhuma relação semântica é criada. EID/SIN e a presença de BCNF recebem notas de revisão, assim como questões já registradas no documento de origem.

O arquivo data/extraction/glossary-v2/concept-definitions.jsonl é uma fila de **candidatos pendentes**, não um JSON de conceitos aprovados para o grafo. Não contém tradução portuguesa revisada nem validação conceitual de todas as definições; as fontes podem conter simplificações e problemas. Esses candidatos não foram misturados à união aprovada.

Para repetir:

```powershell
python scripts/extract-glossary-concepts.py --output data/extraction/glossary-v3
```

## Verificações e limites

Os 35 testes passaram. As 72 citações dos glossários foram confrontadas com seus offsets originais, os IDs de candidato são únicos e todos mantêm status pending. A união aprovada passou na validação de esquema, referências e citações.

Esta rodada aumenta a base de definições rastreáveis e recupera relações que antes foram perdidas, mas ainda não conclui uma extração ampla e revisada dos nove documentos. Falta revisar os candidatos dos glossários, resolver equivalências como sinônimos e flexões, melhorar cobertura das relações e tratar as pendências das fontes e das figuras. A execução e a documentação estão locais; não foram publicadas automaticamente no GitHub nesta rodada.
