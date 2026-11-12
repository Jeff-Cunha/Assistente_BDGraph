# Interface e visualização (parte 5)

Aplicação web local que recebe uma pergunta em português, consulta o grafo do Neo4j, pede a
resposta ao modelo local e mostra na tela **a resposta, as evidências literais, o nível de
sustentação, a consulta Cypher executada e o subgrafo percorrido**.

## 1. Como rodar

Pré-requisitos: Neo4j com o grafo da parte 2 carregado e Ollama com um modelo instalado.

```bash
python -m pip install -r requirements-interface.txt

# Neo4j (Windows, sem serviço instalado): use o atalho
#   C:\Users\Public\bdgraph-setup\subir-neo4j.cmd
# ou, no git-bash:
cd /c/tools/neo4j && export JAVA_HOME="C:\Program Files\Java\jdk-21.0.12"
nohup ./bin/neo4j.bat console > /c/tools/neo4j/console.log 2>&1 &

# interface
cd "/c/Users/Jotapê/Documents/Projetos/Assistente_BDGraph"
python -m uvicorn app.interface:app --host 127.0.0.1 --port 8000
```

Abrir `http://127.0.0.1:8000`. A senha do banco vem do `.env` do projeto, como nas partes 2 e 4.

## 2. O que a tela mostra

| Bloco | Origem | Para que serve |
|---|---|---|
| Resposta | `answer.answer_pt` | texto em português, no máximo cinco frases |
| Afirmações | `answer.claims` | cada afirmação carrega os identificadores de evidência |
| Evidências | `answer.citations` | citação literal em inglês, trecho e documento |
| Sustentação | `answer.support` | nível, cobertura, trechos e documentos distintos, citações não verificadas |
| Subgrafo | `answer.graph.paths` | nós e arestas do caminho percorrido, com a citação de cada aresta |
| Consulta | `answer.graph.cypher` + `parameters` | exatamente o que foi executado no banco |
| Leitura da pergunta | `answer.reading` | qual conceito foi reconhecido e por que aquele caminho |
| Modo de recuperação | `answer.mode`, `answer.graph.channels` | híbrida (vetor + grafo) ou grafo (plano Cypher) |
| Limitações | `answer.limitations` | o que o indicador não significa |

O contrato consumido é o mesmo `answer.json` da parte 4 (`schemas/answer.schema.json`): a
interface não inventa campos nem reescreve texto.

## 3. Arquitetura

```
navegador ──POST /api/ask──► interface.py ──fila──► engine.answer_question()
   ▲                              │                        │
   └──GET /api/job/{id} (2s)──────┘                        ├─ planner.build_plan()
                                                           ├─ guard.compile_plan()
                                                           ├─ executor.execute_plan()
                                                           ├─ bundle_from_paths()
                                                           └─ grounding.evaluate()
```

| Arquivo | Papel |
|---|---|
| `app/interface.py` | API HTTP, fila de trabalhos, página inicial |
| `app/engine.py` | carrega os scripts das partes 2–4, executa o pipeline, guarda cada execução |
| `app/planner.py` | transforma a pergunta livre em plano de consulta validado |
| `app/static/index.html` | estrutura da página |
| `app/static/app.js` | fila de polling, render das seções e desenho do subgrafo em SVG |
| `app/static/styles.css` | folha de estilo (papel, serifa, mono) |
| `app/static/fonts/` | fontes servidas localmente; a tela não depende de CDN |
| `tests/test_interface.py` | 17 testes sem banco e sem modelo |

## 4. Modos de recuperação

O seletor da lateral escolhe de onde vêm as evidências:

| Modo | O que faz | Precisa de Neo4j? | Mostra Cypher? |
|---|---|---|---|
| `hybrid` (padrão) | `scripts/retrieval.py` da parte 3: busca vetorial sobre os 59 trechos somada à travessia do grafo por fusão de ranks, com caminho mais curto e centralidade de grau | não | não |
| `graph` | plano de consulta validado contra o Neo4j, com reserva por trecho quando o conceito não tem aresta | sim | sim |

O modo híbrido carrega um codificador de frases na primeira pergunta (`sentence-transformers`,
dependência de `requirements-retrieval.txt`) e usa `data/retrieval/chunk_embeddings.json`, já
versionado. No modo híbrido o subgrafo é montado a partir das relações realmente usadas pelo
pacote de evidências, com a citação de cada aresta.

## 5. Decisões

- **Um trabalho por vez.** O modelo local responde em ~2 min nesta máquina; uma fila com um
  único worker evita duas gerações concorrentes disputando a GPU. A página faz polling a cada
  1,8 s e mostra o passo atual.
- **Nada é reimplementado.** `engine.py` carrega `guard-cypher.py`, `neo4j-executor.py`,
  `answer-grounding.py` e `run-answer-ollama.py` exatamente como estão. Correção na parte 2, 3
  ou 4 chega à tela sem cópia.
- **A pergunta livre não vira Cypher escrito pelo modelo.** O planejador liga a pergunta aos
  conceitos do grafo e monta saltos que **existem** no banco; o guard valida o plano de novo
  antes da execução. A mesma pergunta produz sempre a mesma consulta.
- **Reserva por trecho.** Quando o conceito ainda não tem relação semântica no grafo (o caso de
  dois terços dos 93 conceitos neste corpus), a consulta vai pelas arestas estruturais
  `MENTIONS` e a citação é cortada literalmente do texto do trecho. A tela diz qual dos dois
  caminhos foi usado em `reading.strategy` (`shortest-path`, `walk` ou `text`).
- **Falha aparece como falha.** Pergunta fora do grafo, resposta reprovada na verificação e
  modelo fora do ar geram estados distintos na tela, nunca um texto entremeado.
- **Sem CDN.** Fontes locais e grafo desenhado em SVG puro: a demonstração funciona sem internet.

## 6. Endpoints

| Método | Rota | Resposta |
|---|---|---|
| `GET` | `/` | página |
| `GET` | `/api/health` | Neo4j (nós e relações semânticas), Ollama, modelos, modelo padrão |
| `GET` | `/api/models` | modelos locais disponíveis (nuvem é recusada) |
| `GET` | `/api/concepts` | os 93 conceitos do grafo |
| `GET` | `/api/suggest?q=` | conceitos que casam com o texto digitado |
| `POST` | `/api/ask` | `{question, mode?, model?}` → `{job_id, model}` |
| `GET` | `/api/job/{id}` | `status`, `step`, `answer` ou `message`/`suggestions` |
| `GET` | `/api/runs` | execuções salvas, mais recente primeiro |
| `GET` | `/api/runs/{id}` | `answer.json` da execução |

Estados de trabalho: `queued`, `running`, `done`, `unmatched`, `rejected`, `error`.

## 7. Testes

```bash
python -m pytest -q tests/test_interface.py     # 17 testes, sem banco e sem modelo
```

Cobrem: ranqueamento de conceitos (frase específica vence palavra genérica, plural e acento),
corte literal da citação, plano de reserva aceito pelo guard, página servida, pergunta curta
recusada, pergunta sem correspondência mantendo sugestões, falha do modelo exposta, saúde dos
dois serviços e sugestões usando o vocabulário do grafo.

## 8. Problema conhecido: credencial do git neste computador

O OpenBot injeta em cada comando do git um helper de credencial para `github.com`
(`GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_*`) que devolve o token do **app do OpenBot**. Esse app não
tem este repositório liberado, então `git push` falha com:

```
remote: Write access to repository not granted.
fatal: ... The requested URL returned error: 403
```

A permissão da conta está correta (`permissions.push: true` na API); o problema é qual
credencial o git usa. Para empurrar com o token pessoal gravado no cofre do OpenBot:

```bash
GIT_CONFIG_COUNT=0 GIT_TERMINAL_PROMPT=0 git \
  -c credential.helper='!f() { test "$1" = get || exit 0; echo username=x-access-token; \
  printf "password=%s\n" "$(cat "/c/Users/Jotapê/AppData/Roaming/OpenBot/agent-api-keys/.vault/GITHUB_TOKEN")"; }; f' \
  push -u origin entrega/parte5-interface
```

Em outra máquina, sem OpenBot, `git push` normal funciona e nada disso é necessário.

## 9. Limites conhecidos

- Cada pergunta custa ~2 min com `qwen3:8b` na GTX 1650 (4 GB). `qwen3:4b` responde mais rápido
  com qualidade menor; o seletor da tela lista o que estiver instalado.
- O grafo de exemplo tem 23 relações semânticas para 93 conceitos, então a maioria das perguntas
  cai na reserva por trecho.
- Trabalhos ficam em memória: reiniciar o servidor perde a fila, mas não as execuções salvas em
  `work/interface-runs/`.
- A tela não tem autenticação e escuta apenas em `127.0.0.1`.
- O modo híbrido depende de `sentence-transformers`; sem ele, a interface responde em modo grafo
  e reporta o erro em vez de degradar em silêncio.
