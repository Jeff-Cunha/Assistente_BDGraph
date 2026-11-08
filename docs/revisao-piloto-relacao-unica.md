# Piloto com relação única e verificação separada

Foi ajustado o piloto local para propor no máximo uma relação por passagem. O texto da evidência continua sendo selecionado por ID e copiado do original com offsets; não é gerado nem reparado pelo modelo.

## Mudanças

- Validação de no máximo uma proposta por chamada.
- Segunda chamada do mesmo Qwen3 8B verifica sustentação, direção, categoria dos endpoints e condições.
- Política conservadora bloqueia REQUIRES quando a passagem contém uma proposição subordinada "requires that", alternativas "must ... or" ou condições explícitas reconhecidas. Isso sinaliza revisão, não prova que toda proposta desse tipo seja falsa.
- Controles sintéticos são identificados e nunca podem liberar conteúdo para o corpus.
- IDs inválidos, endpoints não literais, gerações truncadas e respostas com tipos incorretos continuam rejeitados.
- Execuções futuras preservam instrução, hash do script e parâmetros no próprio diretório de resultados.

Não há aprovação semântica automática. Passar na verificação do modelo mantém review_status=pending. A revisão por Codex que produziu a pequena saída final foi registrada separadamente, sem alterar as propostas ou respostas originais.

## Execuções feitas

### Versão intermediária, antes da política conservadora

Diretório: data/extraction/passage-pilot-v2.

Cinco passagens já usadas no piloto anterior e dois controles negativos sintéticos. Duas propostas passaram pela verificação do próprio modelo; uma delas era a formulação inadequada de integridade referencial REQUIRES chave estrangeira. A segunda chamada repetiu o erro do gerador, demonstrando que autoverificação não é uma avaliação independente.

### Versão com bloqueio de requisitos qualificados

Diretório: data/extraction/passage-pilot-v3.

Sete passagens reais (as cinco anteriores e duas novas) e dois controles sintéticos. Resultado do pipeline:

| Grupo | Passaram pela triagem | Rejeitados/bloqueados | Abstenção |
|---|---:|---:|---:|
| Sete passagens do corpus | 2 | 5 | 0 |
| Dois controles negativos | 0 | 1 | 1 |

No primeiro controle o modelo propôs uma relação e o verificador a bloqueou; no segundo o extrator se absteve. Não confundir bloqueio posterior com abstenção correta do gerador.

As duas propostas conservadas foram conferidas por Codex com a evidência e mantidas na saída revisada:

- entity integrity → REQUIRES → primary key, limitada à regra conceitual apresentada pela fonte.
- join → COMBINES → rows, apoiada na explicação de combinação de linhas.

O nome canônico row e a tradução linha foram atribuídos na revisão a partir da forma literal rows. Esse ajuste de nomenclatura não muda a citação nem a proposta original, que permanece nos logs.

O arquivo extraction-reviewed.json contém 4 conceitos, 2 relações e 6 referências literais e passou no validador do contrato 0.1.0. Os controles não constam desse arquivo. A soma dos tempos registrados nas chamadas foi 21,23 segundos, sem contar todo overhead do processo; não é benchmark geral de desempenho.

## Limitações observadas

O verificador recusou self join IS_A join e sugeriu a direção inversa. A revisão por Codex identifica a justificativa como inadequada e registra um possível falso negativo; não foi feita reinserção automática. Portanto, o mecanismo pode tanto repetir erros do gerador quanto rejeitar afirmações aproveitáveis.

O conjunto é pequeno, selecionado e já usado para ajustar o processo. Não calcular precisão ou declarar eficácia comprovada a partir dele. As revisões por Codex não substituem conferência humana independente. A política de requisitos qualificados é um filtro de alta cautela, com perda de cobertura, e não um analisador lógico completo.

## Verificações

18 testes passaram: 9 de consolidação e 9 de integridade/verificação por passagens. Cobrem, entre outros casos, o bloqueio da formulação condicional mesmo quando o modelo poderia aprová-la, rejeição de booleanos em forma de string e preservação das evidências originais.

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/passage-pilot-v3/extraction-reviewed.json
```

Repetir o piloto em novo diretório:

```powershell
python scripts/pilot-passage-extraction.py --output data/extraction/passage-pilot-v4 --limit 7 --semantic-check --negative-controls
```

O número máximo atual de passagens reais é sete; este script não processa todo o corpus. Para ampliar a D03 e D07 completos, a seleção deve virar um lote de passagens com fila de revisão, preservando as recusas e sem usar a aprovação do mesmo modelo como decisão final.
