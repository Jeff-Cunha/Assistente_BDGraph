# Roteiro da apresentação — 11 min 25 s

12 slides. Os tempos abaixo somam **685 s (11 min 25 s)**, deixando folga no limite de 12.
As notas equivalentes estão nos comentários de cada slide do `slides.pptx`.

| # | Slide | Tempo | O que precisa sair da boca |
|---|---|---:|---|
| 1 | Capa | 0:20 | O que o trabalho entrega, em uma frase: respostas sobre banco de dados com fonte conferível |
| 2 | Fluência não é rastreabilidade | 0:50 | Os três problemas: sem fonte não se confere; similaridade não é cadeia de fatos; alucinação |
| 3 | Como isso virou requisito | 0:40 | A frase da pergunta de projeto e as três obrigações que ela cria |
| 4 | Quatro pilares | 0:55 | O desenho do enunciado e as duas decisões próprias: o modelo não escreve Cypher; o nível não vem do modelo |
| 5 | O que entrou, com número | 0:45 | 9 / 59 / 93 / 23 / 134 / 6 e o gargalo das relações dito de frente |
| 6 | Dois canais, uma lista | 1:10 | Vetor resolve idioma, grafo resolve cadeia; RRF soma sem calibrar; os três modos |
| 7 | O modelo não escreve Cypher | 0:55 | Plano em vocabulário fechado, compilação, guard; 38 casos de ataque |
| 8 | Cada afirmação aponta para o texto | 0:55 | Citação verificada literalmente; nível por regra; high/medium/low/insufficient |
| 9 | A resposta inteira numa tela | 0:55 | Percorrer a tela da esquerda para a direita, apontando cada prova |
| 10 | 45 execuções | 1:20 | O gráfico, o 1/5 → 4/5 → 5/5 e a abstenção 5/5 |
| 11 | O que este resultado não prova | 0:40 | Os quatro limites, sem rodeio |
| 12 | Roteiro de três minutos | 2:00 | A demonstração ao vivo |

## Antes de começar (checklist de 2 minutos)

```bash
cd /c/tools/neo4j                       # ou o .cmd em C:\Users\Public\bdgraph-setup
export JAVA_HOME="C:\Program Files\Java\jdk-21.0.12"
nohup ./bin/neo4j.bat console > console.log 2>&1 &
# outra janela:
cd "C:\Users\Jotapê\Documents\Projetos\Assistente_BDGraph"
python -m uvicorn app.interface:app --host 127.0.0.1 --port 8000
ollama list                             # qwen3:8b tem de aparecer
```

Abrir `http://127.0.0.1:8000` e **clicar numa execução salva** antes de falar. Isso deixa a tela
pronta; se a GPU demorar, você abre a mesma pergunta já respondida e diz que é o mesmo sistema.

## Fala de cada slide

**1. Capa (0:20).** "Vou mostrar um assistente que responde perguntas sobre bancos de dados e,
em cada afirmação, aponta o trecho exato do documento que a sustenta."

**2. Problema (0:50).** "Três fatos guiaram o projeto. Primeiro: resposta sem fonte verificável não
se confere — em ensino, vale o mesmo que não responder. Segundo: busca vetorial acha passagem
parecida, não a cadeia de fatos. Terceiro: perguntar de verdade exige atravessar documentos."

**3. Requisito (0:40).** Ler a pergunta de projeto em voz alta. "Isso virou três obrigações:
corpus real e licenciado, citação literal conferida, e abster quando não há evidência."

**4. Arquitetura (0:55).** "São os quatro pilares do enunciado. Duas decisões são nossas: o modelo
não escreve Cypher, ele escolhe um plano em vocabulário fechado; e o nível de sustentação é
calculado por regras, não informado pelo modelo."

**5. Números (0:45).** "Nove documentos, 59 trechos, 93 conceitos, 23 relações, 134 menções e seis
índices. E o gargalo, dito de frente: 23 relações para 93 conceitos limitam o multi-hop."

**6. Híbrida (1:10).** "O vetor resolve o descompasso de idioma: corpus em inglês, pergunta em
português. O grafo resolve a cadeia. A fusão por ranks soma os dois sem calibrar escores."

**7. Cypher (0:55).** "O modelo recebe a pergunta e devolve um plano: nó inicial, direção, tipos e
limite. O sistema compila. O guard confere rótulo, tipo, orçamento de saltos e LIMIT. São 38 casos
de ataque, 32 com recusa obrigatória."

**8. Fundamentação (0:55).** "Cada citação é conferida literalmente contra o texto do trecho.
Se o modelo inventar a frase, a afirmação é descartada e o nível cai. O modelo é proibido de
informar confiança."

**9. Interface (0:55).** Percorrer com o dedo: "pergunta e modo; resposta com marcadores E1;
painel que diz por que é média; subgrafo com nomes e tipos; fontes com link; citação literal."

**10. Avaliação (1:20).** "Mesmo modelo, mesmo prompt, mesmas regras: muda só a recuperação.
No grupo multi-hop, o vetor puro acerta 1 de 5; o híbrido, 4; o plano, 5. E o número que mais
importa: abstenção 5 de 5 nos três modos — nenhum respondeu pergunta fora do corpus."

**11. Limites (0:40).** "Quatro limites: cobertura das relações, circularidade parcial do gabarito,
amostra de 15 perguntas e ausência de revisão humana independente."

**12. Demonstração (2:00).** Seguir o roteiro do slide. Fechar com a recusa da receita de bolo:
"preferir não responder é a funcionalidade, não a falha."

## Demonstração — ordem exata

1. **Perguntar pelo grafo** (modo `hybrid`): *"Quais relações ligam integridade referencial a
   chaves estrangeiras?"* — leva de 1 a 3,5 min; comece a falar enquanto roda.
2. **Apontar a prova:** marcadores `E1`, painel de sustentação, subgrafo, citação literal.
3. **Pedir o que não existe:** *"receita de bolo de cenoura"* — a tela mostra a recusa com
   sugestões. Nunca clique em `CONSULTAR` duas vezes seguidas: a fila é de um trabalho por vez.

Se a GPU travar: abra a execução salva `763271cb3682` (ou a mais recente) e diga que é a mesma
pergunta, mesmo modelo, 100% das citações verificadas.

## Perguntas prováveis, com resposta curta

| Pergunta | Resposta |
|---|---|
| Por que não usar LangChain ou LlamaIndex? | O enunciado permite; o que precisávamos não vem pronto: extração com evidência por aresta, guard que recusa Cypher livre e verificação literal de citação. |
| Qual a diferença entre GraphRAG e KAG? | GraphRAG constrói o grafo do próprio corpus; KAG usa conhecimento com esquema e semântica explícitos. Aqui o esquema é fechado e cada aresta carrega citação — por isso a verificação é possível. |
| A resposta está certa? Como sabem? | O critério é mecânico: documento esperado entre as fontes e nenhuma citação não verificada. O texto da resposta não é julgado — está nos limites. |
| Por que só 23 relações? | É o custo de extrair e revisar com rastreabilidade. Já está declarado como o principal fator limitante. |
| Por que o nível é médio se a resposta está certa? | O nível mede a procedência das citações, não a correção: uma resposta apoiada em um único documento é `medium` por regra. |
| Isso escala? | A ingestão é idempotente e o índice vetorial é nativo; o gargalo é a extração, que hoje passa por revisão humana. |
