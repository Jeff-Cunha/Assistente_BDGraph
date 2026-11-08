# Preparação do pipeline automático

Estado atual: entradas piloto preparadas e adaptador Gemini implementado, sem execução de modelo. Configuração inicial: gemini-3.8-flash, dependendo de disponibilidade e cota gratuita da conta. Houve tentativas de API sem extração validada; a extração local e seus resultados estão descritos em docs/cobertura-sql.md. Consulte `docs/configuracao-gemini.md`.

## Arquivos

- `scripts/prepare-extraction.py`: preparação independente de provedor, usando apenas a biblioteca padrão do Python.
- `schemas/extraction-candidates.schema.json`: formato da resposta de candidatos por trecho.
- `docs/prompt-extracao.md`: instruções de extração e limites.
- `data/extraction/pilot-inputs/requests.jsonl`: oito entradas dos seis trechos de D03 e dos dois de D07.
- `data/extraction/pilot-inputs/manifest.json`: IDs e hashes da entrada, instruções e esquema.

O arquivo requests.jsonl é um formato interno, não um arquivo de batch pronto para qualquer API. Cada adaptador deverá converter as instruções, o esquema e a entrada ao formato do provedor escolhido.

## Preparar um novo lote

Python 3.10 ou superior; execução verificada com Python 3.13 disponível neste computador.

```powershell
python scripts/prepare-extraction.py --documents D03 D07 --output data/extraction/pilot-inputs-v2
```

O comando não sobrescreve diretórios não vazios nem permite saída fora do projeto. Por padrão não inclui suplementos. Para incluí-los, usar `--include-figures`; seus detalhes incertos ainda precisam de triagem antes de aceitar relações. O lote inicial não inclui figuras e não substitui a leitura dos suplementos.

O registro conhecido inicial contém somente nomes, aliases e IDs dos 12 conceitos da amostra, sem citações nem relações esperadas. Essa inicialização auxilia a resolução, mas impede tratar o piloto como avaliação independente.

## Etapas ainda necessárias

1. Configurar chave Gemini local e confirmar elegibilidade/cota Free Tier na conta.
2. Executar primeiro teste com `scripts/run-extraction-gemini.py --limit 1`; adaptador inclui timeout, interrupção em erro, logs sem credenciais e persistência de resposta original.
3. Inspecionar os candidatos; o adaptador valida esquema, IDs locais, citações literais e referências ao trecho.
4. Resolver entidades com registro persistente. Equivalências ambíguas devem permanecer em revisão.
5. Converter ao contrato final 0.1.0, reunir evidências e validar com `scripts/validate-extraction.ps1`.
6. Revisar semanticamente os candidatos antes de liberar a ingestão no Neo4j.

O preparador só organiza entradas. O adaptador Gemini valida candidatos; a consolidação conservadora e a resolução revisada estão implementadas; equivalências ambíguas continuam pendentes. O validador PowerShell atual é para a saída consolidada, não para as respostas brutas por trecho.

## Verificações já executadas

- Oito entradas com IDs únicos e documentos corretos.
- Textos de entrada não vazios e vocabulário sem evidências/respostas da amostra.
- Diretório de lote existente protegido contra sobrescrita.
- Amostra consolidada continua válida: 12 conceitos, 9 relações e 21 citações literais.

Não foram feitos testes de qualidade de um modelo, extração automática real ou ingestão no banco nesta etapa.
