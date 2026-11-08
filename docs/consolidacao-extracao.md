# Consolidação das extrações

Esta etapa é independente do provedor de IA. Recebe os candidatos de cada trecho e entrega um JSON no contrato 0.1.0 para revisão e futura ingestão no Neo4j. Não faz chamadas de modelo nem altera corpus, credenciais ou configurações do Ollama.

## Comportamento

1. Valida candidatos contra o esquema e as citações literais nos 59 trechos do corpus.
2. Confere IDs locais e referências propostas ao registro canônico.
3. Reutiliza IDs do registro quando o nome/alias corresponde explicitamente, ou quando há nome canônico idêntico após normalizar espaços, caixa e Unicode.
4. Gera IDs determinísticos para nomes novos, com hash para reduzir colisões.
5. Acumula evidências sem duplicá-las e reúne relações de mesma origem, tipo e destino.
6. Registra aliases ambíguos, descrições alternativas e observações do modelo em review.json. Aliases compartilhados não provocam fusão automática.
7. Mantém todos os itens pending ou flagged, propagando pendências dos conceitos às relações.

Equivalência semântica não é resolvida apenas com normalização textual. Se o modelo indicar um ID conhecido incompatível com o nome, ou houver conflito de categoria, a operação para e requer resolução manual. Não há aprovação automática de fatos.

O registro inicial é a amostra manual sample.json. Seu uso fornece vocabulário, mas não copia relações, evidências ou aprovações antigas para os novos resultados. O arquivo de entrada pode incluir respostas com issues; essas observações são mantidas, não resolvidas.

## Executar quando houver candidatos reais

Na raiz, com requirements-extraction.txt instalado:

```powershell
python scripts/consolidate-extraction.py --candidates data/extraction/SEU_LOTE/extract_D03_C001.candidates.json --output data/extraction/consolidated-v1
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/consolidated-v1/extraction.json
```

Substituir SEU_LOTE pelo diretório real. Passar arquivos individuais, explicitamente, após escolher uma resposta por chunk. Podem ser fornecidos vários caminhos após --candidates. Não misturar respostas de diversas tentativas do mesmo trecho.

Saídas: extraction.json (conceitos e relações com evidências) e review.json (mapeamentos locais/canônicos, pendências e hashes das entradas). Não há sobrescrita de diretório não vazio. Use --registry para indicar um registro canônico posterior à amostra inicial. O registro deve conter concepts com os mesmos campos do contrato.

## Verificar o código

```powershell
python -m unittest discover -s tests -p test_consolidation.py -v
```

Os testes usam textos sintéticos exclusivamente para validar estrutura, resolução e falhas. Não são documentos do corpus nem resultados reais de um modelo. A qualidade da extração dependerá de testes separados com o modelo instalado.

## O que falta após a instalação do Ollama

Executar uma extração real, revisar a qualidade, consolidar o lote selecionado e revisar as pendências antes da carga no Neo4j. Dados pending/flagged podem entrar em ambiente de inspeção, mas não devem ser tratados como conhecimento aceito no sistema final de respostas.
