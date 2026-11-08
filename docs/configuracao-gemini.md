# Configuração da extração com Gemini

Configuração inicial: Gemini API, modelo `gemini-3.8-flash`. A documentação consultada lista entrada e saída gratuitas na faixa Free Tier; disponibilidade e cotas dependem da conta/projeto. O programa não verifica nem impõe a modalidade de faturamento do Google.

## Preparar o acesso

1. Abrir https://aistudio.google.com/apikey e entrar com a conta Google.
2. Criar uma chave em um projeto elegível para Free Tier e conferir a modalidade e os limites no AI Studio. Não ativar faturamento para seguir o objetivo de gratuidade.
3. Na raiz local do projeto, copiar `.env.example` para `.env`.
4. Preencher GEMINI_API_KEY no arquivo local. Nunca enviar a chave ao chat, WhatsApp ou GitHub. O arquivo .env está no .gitignore.

O leitor de .env aceita somente GEMINI_API_KEY e GEMINI_MODEL, em linhas simples chave=valor, sem interpolação. Variáveis de ambiente têm precedência.

## Execução

```powershell
python -m pip install -r requirements-extraction.txt
python scripts/run-extraction-gemini.py --dry-run
python scripts/run-extraction-gemini.py --limit 1
```

A última linha realiza uma chamada real com um trecho e o vocabulário do projeto. A cota gratuita pode ser insuficiente ou indisponível; resposta 429 interrompe a execução sem retentativas automáticas. Confirme a disponibilidade do modelo na sua conta; se necessário, altere GEMINI_MODEL para outro modelo compatível, conferindo os preços antes.

As respostas originais, os candidatos validados e o manifesto são salvos em data/extraction/pilot-results. Se a geração for truncada, bloqueada, contiver evidência inventada ou violar o esquema, não será salva como candidata validada. A resposta bruta disponível permanece para inspeção. Um erro interrompe o lote.

O script não sobrescreve um diretório não vazio. Para um novo teste, usar `--output data/extraction/pilot-results-v2`. A opção `--delay` regula a pausa entre chamadas; não garante respeito a todas as cotas do projeto.

## Limites

- Modo JSON solicitado à API; esquema e referências são validados localmente. Não há garantia de acerto semântico.
- O corpus é público, mas a faixa gratuita pode utilizar dados para melhoria de produtos conforme as condições do provedor. Não enviar documentos privados sem avaliar as condições.
- Os resultados continuam pending ou flagged: não são fatos aprovados para ingestão.
- A resolução de entidades e a conversão ao contrato consolidado ainda serão implementadas.
- A integração ainda não produziu uma extração real validada. Nas tentativas iniciais, o modelo 2.5 Flash foi recusado para novos usuários e o 3.8 Flash retornou alta demanda; credenciais e logs dessas tentativas não fazem parte do repositório.

## Referências consultadas

- https://ai.google.dev/gemini-api/docs/pricing.md
- https://ai.google.dev/gemini-api/docs/api-key
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://ai.google.dev/api
