# Ollama: instalação e configuração

Atualização: o usuário decidiu executar o modelo no computador principal. Consulte `docs/modelo-local-principal.md` para a instalação e os testes efetivamente realizados. O planejamento de rede/notebook abaixo fica preservado como histórico e não é necessário para a configuração atual.

Registro iniciado em 08/11/2026. Ollama confirmado no Windows pela API local, versão 0.40.15, sem modelos instalados. Usuário informou instalação também no notebook; a verificação desse equipamento e os testes de modelo/rede ainda estão pendentes.

## Equipamentos e estado verificado

| Papel | Equipamento | Estado |
| --- | --- | --- |
| Principal: código, Neo4j e interface | Windows 11 Pro 64 bits; i5-10400F, 6 núcleos/12 threads; aproximadamente 16 GB RAM; RTX 3060, 12 GB VRAM; driver 616.92 | Ollama 0.40.15 instalado e respondendo em 127.0.0.1:11434; lista de modelos vazia |
| Servidor do modelo pretendido | ASUS Vivobook M1502YA-NJ611; Ryzen 7 5825U; 8 GB RAM; Radeon integrada; Manjaro confirmado pelo usuário | Instalação informada pelo usuário; versão do Ollama, espaço livre, modelos e IP ainda aguardam consulta no notebook |

Principal: Ethernet em rede privada, IPv4 observado `192.168.0.3`. Esse endereço pode mudar por DHCP. Cerca de 31 GiB livres no C: e 453 GiB no F: na consulta inicial. O IP do notebook não foi presumido.

O principal tem uma GPU suportada pelo Ollama e provavelmente será um servidor mais rápido, mas a configuração pretendida mantém o notebook dedicado ao modelo. Instalar o aplicativo nos dois não exige baixar o modelo nos dois. Inicialmente, baixar somente no notebook.

## 1. Conferir o notebook (Manjaro)

Executar no terminal do notebook:

```bash
cat /etc/os-release
uname -m
free -h
df -h / /home
command -v ollama
ip -4 -brief address
```

Se Ollama já existir, consultar `ollama --version`, `ollama list` e `systemctl status ollama --no-pager` antes de qualquer reinstalação. Não misturar instalação por pacote da distribuição e instalador oficial sem conferir a origem existente.

## 2. Instalar após a conferência

Windows principal: instalador oficial `https://ollama.com/download/OllamaSetup.exe`, com assinatura digital válida de Ollama Inc. Instalação por usuário, sem baixar modelos. Verificar `ollama --version` e `http://127.0.0.1:11434/api/version`. O aplicativo já mantém um servidor em segundo plano; não iniciar outro `ollama serve`.

Manjaro notebook: se não houver instalação existente e houver espaço suficiente, a documentação oficial Linux indica:

```bash
curl -fsSL https://ollama.com/install.sh | sh
systemctl status ollama --no-pager
ollama --version
curl -fsS http://127.0.0.1:11434/api/version
```

O instalador Linux pode solicitar a senha local de administrador. Não enviar a senha no chat. Se houver falha, guardar a mensagem antes de tentar outro método. Planejar execução por CPU; aceleração da Radeon integrada não foi verificada. Não instalar drivers ROCm apenas por haver uma Radeon.

## 3. Modelo e teste local no notebook

Modelo inicial proposto: `qwen3:1.7b`, aproximadamente 1,4 GB de download no catálogo consultado. A RAM utilizada é maior que o arquivo. A velocidade e a qualidade precisam ser medidas.

Com 8 GB RAM, fechar aplicativos desnecessários e começar com uma requisição por vez e contexto de 4096 tokens. Configurar o serviço com `sudo systemctl edit ollama`, preservando eventuais opções existentes:

```ini
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_CONTEXT_LENGTH=4096"
Environment="OLLAMA_NO_CLOUD=1"
```

Aplicar com `sudo systemctl daemon-reload` e `sudo systemctl restart ollama`. Primeiro manter acesso somente local.

```bash
ollama pull qwen3:1.7b
curl -fsS http://127.0.0.1:11434/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3:1.7b","messages":[{"role":"user","content":"Responda em JSON com a chave definicao: o que é uma chave primária em um banco relacional?"}],"format":"json","think":false,"stream":false,"options":{"num_ctx":4096,"num_predict":256,"temperature":0},"keep_alive":"2m"}'
ollama ps
free -h
```

Registrar tempo, memória disponível, uso de CPU/GPU e conteúdo. JSON válido não comprova correção semântica. O piloto acadêmico ainda deverá preservar esquema, IDs, citações literais e estados pending/flagged; os oito pedidos existentes não foram executados no Ollama nesta etapa. Se o contexto completo exceder a janela, ajustar explicitamente e medir memória; não truncar silenciosamente o texto ou o contrato.

## 4. Rede privada — pendente dos endereços e firewall reais

Primeiro identificar o IP privado do notebook, confirmar que os equipamentos estão na mesma rede e verificar qual firewall está ativo no Manjaro. Não desativar firewall, não abrir portas no roteador e não criar túneis públicos.

No serviço do notebook, adicionar `Environment="OLLAMA_HOST=IP_PRIVADO_DO_NOTEBOOK:11434"` com o endereço real. Antes de reiniciar, preparar regra de entrada TCP 11434 restrita ao IP real do principal, na interface/rede privada. Inspecionar regras existentes: uma liberação ampla anterior anularia a restrição pretendida. A sintaxe da regra depende do firewall encontrado; ainda não foi escolhida nem aplicada. A API local não deve ficar acessível a outros equipamentos.

Após reiniciar o serviço, testar no PowerShell do principal, substituindo o endereço:

```powershell
Invoke-RestMethod -Uri 'http://IP_PRIVADO_DO_NOTEBOOK:11434/api/version' -TimeoutSec 10
Invoke-RestMethod -Uri 'http://IP_PRIVADO_DO_NOTEBOOK:11434/api/tags' -TimeoutSec 10
```

O cliente Python pode chamar esse endereço diretamente; não precisa de `OLLAMA_ORIGINS=*`. Manter o servidor do principal em localhost. Não copiar o `.env` nem credenciais Gemini para o notebook. Nenhuma chamada Gemini faz parte desta configuração.

Para endereços estáveis, preferir reservas DHCP no roteador quando disponíveis. Após mudar IP, atualizar escuta, cliente e regra restrita. Para voltar ao acesso local, remover somente a opção OLLAMA_HOST adicionada e a regra específica criada nesta configuração, e reiniciar o serviço.

## Fontes oficiais consultadas

- Windows: https://docs.ollama.com/windows
- Instalador Windows: https://ollama.com/download/windows
- Linux: https://docs.ollama.com/linux
- Variáveis, rede e memória: https://docs.ollama.com/faq
- Hardware: https://docs.ollama.com/gpu
- Modelo: https://ollama.com/library/qwen3:1.7b
- API de chat e JSON: https://docs.ollama.com/api/chat
