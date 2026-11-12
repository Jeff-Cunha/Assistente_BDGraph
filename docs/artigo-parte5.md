# Seção do artigo — Interface, fontes e visualização do subgrafo

> Parte 5 do projeto GraphRAG/KAG sobre bancos de dados e SQL.
> Documento de trabalho; os números marcados como medidos foram obtidos nesta máquina
> (GTX 1650 4 GB, 23 GB RAM, `qwen3:8b`, Neo4j 5.26 local).

## 1. Papel desta etapa no sistema

A parte 5 é a única superfície em que o sistema existe para quem pergunta. Ela não decide
nada sobre extração, grafo, recuperação ou formulação: recebe a pergunta, aciona as etapas
anteriores e apresenta o resultado de modo que a pessoa possa **conferir** a resposta, não
apenas lê-la.

O critério que guiou o desenho foi o do enunciado do trabalho: reduzir alucinação de forma
verificável. Uma resposta sem fonte, sem citação literal ou sem indicação de sustentação não
é considerada entregue — e a interface foi feita para tornar essa ausência visível.

## 2. Problema

Três problemas concretos aparecem quando a saída da parte 4 vai para uma tela:

1. **A pergunta livre não tem plano.** A parte 4 executa um plano de consulta escrito à mão.
   Uma interface precisa aceitar qualquer pergunta em português e ainda assim gerar uma
   consulta determinística, validada e rastreável.
2. **A latência é de minutos, não de milissegundos.** O modelo local leva cerca de dois
   minutos por resposta nesta máquina. Uma página que espera a resposta de forma síncrona
   parece travada e induz o usuário a recarregar e duplicar a execução.
3. **Confiança não se comunica com um número só.** "Sustentação alta" precisa vir junto com
   a citação que a sustenta, o documento de origem e a consulta que recuperou aquilo.

## 3. Método

### 3.1 Pergunta livre → plano validado, sem Cypher escrito pelo modelo

A interface **não** pede ao modelo que escreva Cypher. O planejador (`app/planner.py`):

1. carrega os 93 conceitos do grafo com seus dois nomes (`name_pt`, `canonical_name`);
2. normaliza pergunta e nomes (sem acento, sem plural, sem palavras vazias) e pontua cada
   conceito — nome que aparece como **frase** vence nome que só compartilha palavras, e o
   nome mais longo vence o empate (`chave primária` antes de `chave`);
3. escolhe a estratégia, nesta ordem:
   - `shortest-path`: dois conceitos reconhecidos com caminho de 2 ou mais saltos entre eles;
   - `walk`: o caminho mais profundo e mais frequente que **existe** a partir do conceito principal;
   - `text`: o conceito ainda não tem relação semântica no grafo; a consulta vai pelas arestas
     estruturais `MENTIONS` e a citação é cortada literalmente do texto do trecho.

O plano resultante é validado pelo `guard-cypher.py` da parte 4 antes de qualquer execução.
Como os saltos são copiados de caminhos reais do banco, a mesma pergunta produz sempre a mesma
consulta, e o texto do usuário nunca entra na sintaxe.

### 3.2 Dois modos de recuperação, escolhidos na tela

| Modo | Recuperação | Dependências | Mostra Cypher |
|---|---|---|---|
| `hybrid` (padrão) | busca vetorial sobre os 59 trechos, somada à travessia do grafo por fusão de ranks, caminho mais curto e centralidade de grau (parte 3) | `sentence-transformers` + `chunk_embeddings.json` | não |
| `graph` | plano de consulta validado executado no Neo4j, com reserva por trecho | Neo4j | sim |

Isso resolve a lacuna mais séria da primeira versão: o requisito de **recuperação híbrida** e de
**algoritmo de grafo** passou a existir no sistema que roda, e não apenas no código da parte 3.
O modo híbrido funciona sem o banco no ar, porque a parte 3 lê o grafo dos arquivos de
integração; o modo grafo continua sendo o único que exercita as restrições e os índices do
Neo4j.

Execução medida no modo híbrido pela interface: 108,5 s, 2 afirmações sustentadas, cobertura 1,0,
sustentação `medium` (uma única fonte citada pelo modelo), canais `graph + vector` e três origens
de evidência (`concept`, `graph`, `vector`), com o subgrafo desenhado a partir das duas relações
que o pacote realmente usou.

### 3.3 Execução assíncrona com estados

`POST /api/ask` devolve um identificador e o trabalho entra numa fila com **um único worker**,
porque duas gerações simultâneas disputam a mesma GPU. A página consulta o estado a cada 1,8 s
e mostra o passo corrente ("Interpretando a pergunta", "Consultando o grafo", "Chamando o
modelo local", "Verificando citações").

Estados terminais são distintos de propósito:

| Estado | Significado na tela |
|---|---|
| `done` | resposta com evidências e nível de sustentação |
| `unmatched` | nenhum conceito do grafo na pergunta, com sugestões de termos |
| `rejected` | a resposta do modelo não passou na verificação da parte 4 |
| `error` | banco ou modelo indisponível, com a causa |

Nenhum desses casos é suavizado em texto: uma recusa aparece como recusa.

### 3.4 Apresentação

A tela mostra, na mesma dobra: a resposta em português; cada afirmação com o marcador da
evidência que a sustenta; o painel de sustentação (nível, cobertura, trechos, documentos,
citações não verificadas e as razões calculadas); o subgrafo percorrido; as fontes com link; as
citações literais; e a consulta Cypher executada, com seus parâmetros.

O subgrafo é desenhado em **SVG puro**, com layout por distância na travessia: cada nó recebe
uma coluna conforme o número do salto. É determinístico — a mesma resposta desenha sempre a
mesma figura —, não depende de CDN e permite hover com a citação de cada aresta.

## 4. Implementação

| Arquivo | Papel |
|---|---|
| `app/interface.py` | API HTTP, fila de trabalhos, estados, endpoints de saúde e de execuções |
| `app/engine.py` | carrega os scripts das partes 2–4 sem cópia e executa o pipeline completo |
| `app/planner.py` | pergunta livre → plano validado (`shortest-path`, `walk`, `text`) |
| `app/static/index.html` | estrutura da página |
| `app/static/app.js` | polling, render das seções, layout e desenho do subgrafo |
| `app/static/styles.css` | folha de estilo; fontes servidas localmente em `app/static/fonts/` |
| `tests/test_interface.py` | 17 testes sem banco e sem modelo |

O contrato consumido é o `answer.json` da parte 4 (`schemas/answer.schema.json`). A interface
acrescenta apenas dois campos de leitura — `reading` (como a pergunta foi interpretada) e
`plan` (o plano validado) — e grava cada execução em `work/interface-runs/<id>/answer.json`.

## 5. Resultados obtidos até aqui

Medidos nesta máquina, com o grafo de exemplo (93 conceitos, 59 trechos, 9 documentos,
23 relações semânticas):

| Verificação | Resultado |
|---|---|
| Testes da interface | 17 passando, sem banco e sem modelo |
| Testes das partes 2, 3 e 4 após a integração | 76 + 13 (com `NEO4J_TEST=1`), 85 e 150 passando |
| Pergunta de exemplo ponta a ponta | 114 s; sustentação `high`, cobertura 1,0; 3 de 3 afirmações com evidência; 2 trechos de 2 documentos; 0 citação não verificada |
| Caminho percorrido | `chave estrangeira → junção → junção externa → junção externa à esquerda` (3 saltos) |
| Consulta gerada | `TYPICALLY_USED_IN`, `HAS_FORM`, `HAS_FORM`, com `LIMIT` parametrizado |

## 6. Ameaças à validade

- **Grafo de exemplo pequeno.** Com 23 relações semânticas, a maioria das perguntas cai na
  reserva por trecho; o caminho de 2+ saltos aparece em poucos casos. O resultado mede o
  sistema, não a cobertura do corpus.
- **Um corpus de um único livro-texto.** Duas fontes distintas no exemplo vêm do mesmo site
  (OpenText BC), o que limita a generalização do indicador de sustentação.
- **Revisão pendente no caminho de reserva.** Citações extraídas de trechos sem aresta revisada
  entram como `pending`, e o contrato da parte 4 rebaixa o nível para `low` mesmo com cobertura
  1,0. É conservador de propósito: preferimos um nível baixo explícito a um nível alto que não
  se sustenta na revisão.
- **Um modelo de 8B parâmetro.** A qualidade da resposta depende de `qwen3:8b` rodando em CPU
  parcial; outra máquina produz outro texto (as citações, não: elas são verificadas).

## 7. Limitações e continuidade

- Latência de ~2 min por pergunta; `qwen3:4b` melhora a demonstração ao custo de qualidade.
- Trabalhos ficam em memória: reiniciar o servidor perde a fila, não as execuções salvas.
- A tela não tem autenticação e escuta só em `127.0.0.1`.
- Próximo passo natural: usar o `HybridRetriever` da parte 3 como canal adicional, para que a
  pergunta não dependa apenas do vocabulário dos 93 conceitos indexados.
