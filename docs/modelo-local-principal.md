# Modelo local no computador principal

Decisão de 8 de novembro de 2026: executar o modelo no Windows principal. O notebook não é dependência para essa configuração e não precisa manter conexão pela rede local.

## Ambiente verificado

- Ollama 0.40.15, API em http://127.0.0.1:11434.
- NVIDIA GeForce RTX 3060, 12.288 MiB de VRAM total; 11.674 MiB livres antes do carregamento.
- Modelo qwen3:8b, GGUF Q4_K_M, aproximadamente 5,23 GB no disco.
- Digest: 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41.
- Modelo baixado e integridade verificada pelo Ollama.

A instalação anterior e a configuração inicialmente proposta para notebook permanecem como histórico em docs/configuracao-ollama.md. Este arquivo descreve a decisão atual. Nenhuma porta foi aberta para a rede e nenhuma credencial Gemini é lida pelo adaptador local.

## Adaptador

`scripts/run-extraction-ollama.py` usa a API de chat do Ollama, saída estruturada por JSON Schema e validação local de IDs, estado de revisão e citações exatas. Não existe fallback automático para nuvem. O modelo precisa estar instalado localmente; o script rejeita modelo remoto identificado como cloud.

Parâmetros iniciais de teste: uma chamada por vez, contexto de 16.384 tokens, até 8.192 tokens de resposta, temperatura 0, seed 42 e think=false. A semente não garante igualdade entre versões de runtime ou hardware. Chamadas incompletas e candidatas fora do contrato não são aprovadas silenciosamente.

## Repetir o piloto

Na raiz, com o Ollama aberto e Python/requirements-extraction.txt disponíveis:

```powershell
python scripts/prepare-extraction.py --documents D03 D07 --output data/extraction/pilot-inputs-local-v2
python scripts/run-extraction-ollama.py --input data/extraction/pilot-inputs-local-v2/requests.jsonl --output data/extraction/ollama-pilot-v2 --limit 1
```

Os nomes terminados em v2 são exemplos de nova execução; os diretórios existentes não são sobrescritos. --dry-run verifica as entradas sem chamar o modelo. Em ambientes restritos, o cliente precisa ter permissão para acessar o socket local.

Cada execução preserva resposta original, candidatos que passaram na validação estrutural e manifesto com modelo, digest, versão, parâmetros, tempos e tokens. Validado estruturalmente não significa revisado conceitualmente. Antes da consolidação, conferir se relações, traduções e qualificações estão corretas.

## Próxima etapa

Corrigir as falhas de qualidade da extração antes de ampliar para os oito trechos de D03/D07 e, somente após revisão, para o corpus completo. O esquema e o corpus permanecem inalterados.

## Resultados verificados

- API confirmou o modelo instalado com digest registrado acima.
- /api/ps confirmou modelo inteiramente em VRAM, com size_vram=7.536.965.058 bytes e contexto de 16.384. A GPU registrou atividade de 94% durante uma consulta; esse valor é uma amostra, não média de benchmark.
- Pergunta curta em português sobre chave primária: JSON válido e definição adequada, em 21,42 segundos. Esse tempo inclui eventuais custos de recarregamento; não é estimativa de todas as respostas.
- Primeiro piloto com o vocabulário inicial: geração concluída em 154,57 segundos, 12 conceitos e 11 relações; rejeitado por citações não literais. Inspeção identificou conceitos copiados do registro sem sustentação no trecho e relações generalizadas indevidamente.
- Segundo piloto sem registro, instrução curta e seleção limitada: 38,87 segundos, 8 conceitos e 7 relações; rejeitado por citação não literal. Relações continuaram conceitualmente inadequadas.
- Terceiro piloto em modo JSON simples: 38,62 segundos; rejeitado por violação do esquema, além de problemas de citações e relações observados na inspeção.

Nenhum desses candidatos foi aprovado para consolidação ou ingestão. As respostas brutas e os manifestos estão nos diretórios locais data/extraction/ollama-pilot-v1, v2 e v3. O teste curto está em work/ollama-smoke.json. Esses resultados comprovam execução local, não qualidade suficiente para o pipeline completo.

As falhas sugerem testar extração por passagens menores e separar seleção de evidência da geração de relações, antes de ampliar o lote. Não corrigir citações aproximadas ou inverter relações silenciosamente para fazê-las passar.

Esse teste posterior já foi implementado: consulte `docs/piloto-por-passagens.md`. Cinco passagens foram executadas, com duas relações preservadas após revisão e arquivo consolidado validado. O método de citação melhorou, mas as falhas semânticas ainda impedem uma execução ampla sem revisão.

O preparador agora aceita --no-registry e --prompt para comparar instruções sem alterar o corpus; o adaptador aceita --json-mode. O prompt docs/prompt-extracao-local.md é uma configuração experimental de precisão, limitada a 8 conceitos e 8 relações, não uma extração exaustiva. No modo JSON simples, a resposta ainda passa pela mesma validação local de esquema e evidência.

## Referências

- https://ollama.com/library/qwen3:8b
- https://docs.ollama.com/api/chat
