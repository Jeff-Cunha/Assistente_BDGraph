# Roteiro de fala — 10 min 55 s

Texto para ensaiar em voz alta. Cada bloco começa com o slide e o tempo alvo; o que está escrito é o
que sai da boca, não um resumo. São **1.316 palavras** contadas: a 130 palavras por minuto dão
10 minutos e 7 segundos de fala, mais as pausas da demonstração — **10 min 55 s** no total, dentro
da faixa de 10 a 12. Se você fala mais devagar, perto de 120 palavras por minuto, vai para 11 min 55 s
e ainda cabe.

Os tempos de cada slide foram calculados da contagem de palavras, não estimados no olho. As marcas
`[...]` são de ação, não se falam.

**Antes de começar:** Neo4j no ar, interface em `127.0.0.1:8000`, execução salva aberta na tela.

---

## Slide 1 · Capa — 0:30

Boa noite. Este trabalho é um assistente que responde perguntas sobre banco de dados e que,
em cada afirmação da resposta, aponta o trecho exato do documento que a sustenta. A tela mostra o
grafo que foi percorrido, as fontes e o nível de sustentação. No fim eu faço uma demonstração ao
vivo, com uma pergunta de verdade e uma pergunta que o sistema deve recusar.

## Slide 2 · Fluência não é rastreabilidade — 0:45

Três fatos guiaram o projeto.

O primeiro: uma resposta sem fonte verificável não se confere. Em contexto de ensino isso vale o
mesmo que não responder — e é pior, porque parece conhecimento.

O segundo: busca vetorial recupera passagens parecidas com a pergunta, não a cadeia de fatos que a
responde. Quando a resposta exige ligar dois conceitos que estão em documentos diferentes, o trecho
isolado não resolve.

O terceiro: o modo padrão de falha de um modelo de linguagem é a alucinação, e a literatura sobre
o tema recomenda verificação externa — não confiança no próprio modelo.

## Slide 3 · Como isso virou requisito — 0:35

A pergunta que guiou o projeto foi esta: *a pergunta feita na interface consegue ser respondida com
informação de dois documentos reais, com fonte verificável e o grafo visível?*

Ela virou três obrigações. Corpus real, com licença e URL preservadas por documento. Citação
literal, conferida contra o texto do trecho: se a frase não existe lá, a afirmação cai. E abstenção:
pergunta fora do corpus recebe recusa, não invenção.

## Slide 4 · Quatro pilares — 0:40

São os quatro pilares do enunciado. Extração de entidades e relações do texto; grafo no Neo4j;
recuperação híbrida; e interface com visualização do subgrafo.

Duas decisões são nossas, e são as que mudam o resultado.

Primeira: o modelo não escreve Cypher. Ele escolhe um plano em vocabulário fechado, e o sistema
compila e valida a consulta.

Segunda: o nível de sustentação é calculado por regras, fora do modelo. O modelo é proibido de
dizer o quanto confia na própria resposta.

## Slide 5 · O que entrou, com número — 0:45

O que entrou, com número. Nove documentos abertos, com licença e URL por documento. Cinquenta e
nove trechos: trinta e um de texto e vinte e oito suplementos que transcrevem figuras essenciais.
Noventa e três conceitos, cada um com nome em inglês, nome em português e aliases. Vinte e três
relações semânticas em quatorze tipos. Cento e trinta e quatro menções de trecho para conceito, e
seis índices no banco.

E o gargalo, dito de frente: vinte e três relações para noventa e três conceitos significa que a
maioria dos conceitos não participa de nenhum caminho multi-hop. Isso volta nos limites.

## Slide 6 · Dois canais, uma lista — 1:00

A recuperação tem dois canais, e uma lista só.

O canal vetorial usa MiniLM multilíngue, 384 dimensões, cosseno sobre os 59 trechos. Ele resolve o
descompasso do projeto: o corpus é em inglês e as perguntas são em português.

O canal de grafo percorre as relações semânticas até quatro saltos; usa caminho mais curto quando a
pergunta envolve dois conceitos; e centralidade de grau para priorizar os nós mais conectados.

E o detalhe que importa: cada aresta carrega a citação que a sustenta. A evidência que vem do grafo
não é uma inferência do sistema, é um trecho de documento.

Os dois rankings são somados por fusão de ranks recíprocos, com constante 60 — sem precisar
calibrar escores. Daí saem os três modos que a avaliação compara: só vetor, híbrido e plano Cypher.

## Slide 7 · O modelo não escreve Cypher — 0:50

Aqui está a defesa contra injeção de prompt virar injeção de consulta.

O modelo recebe a pergunta e devolve um plano: nó inicial, direção, tipos de relação e limite.
Texto do modelo nunca vira sintaxe. O sistema compila esse plano em uma consulta de caminho,
parametrizada. E antes de chegar ao banco, o guard confere rótulo, tipo, propriedade, orçamento de
saltos e LIMIT obrigatório.

No repositório há trinta e oito casos de contorno: trinta e dois com recusa obrigatória, cinco de
controle e um limite conhecido, registrado. Escrita, comentário, string literal, procedimento de
extensão, padrão sem rótulo: tudo recusado antes do banco.

## Slide 8 · Cada afirmação aponta para o texto — 0:50

O modelo recebe as evidências como E1, E2, E3 — nunca como URL. Ele devolve afirmações, cada uma
citando identificadores.

Aí o sistema faz quatro coisas: recusa citação de identificador que não existe; confere se a
citação existe literalmente no texto do trecho; descarta afirmação sem evidência; e resolve cada
citação em trecho, seção e URL.

O nível sai das citações verificadas. Alto quando há dois trechos de dois documentos. Médio quando
é um trecho, ou um documento só. Baixo quando a evidência está pendente de revisão. Insuficiente
quando nada sobrevive.

Repare numa coisa: o nível mede procedência, não correção. Uma resposta certa apoiada em um único
documento é média por regra.

## Slide 9 · A resposta inteira numa tela — 0:55

Na tela está a resposta inteira. Em cima, a pergunta e o modo usado. No texto, os marcadores E1 nas
afirmações. À direita, o painel de sustentação, que diz por que aquela resposta é média: cobertura,
número de trechos, de documentos e de citações não verificadas.

Embaixo, o subgrafo percorrido, com os nomes dos conceitos e o tipo de cada aresta. E as fontes com
link, junto da citação literal do trecho — o texto em inglês, como está no documento.

Essa é uma execução real, feita no sistema: duzentos e dez segundos, cem por cento de cobertura.
No modo híbrido aparece o canal usado; no modo grafo aparece a consulta Cypher executada, com os
parâmetros.

## Slide 10 · 45 execuções, mesmas regras — 1:20

A avaliação tem quinze perguntas: cinco conceituais, cinco multi-hop e cinco fora do corpus.
Quarenta e cinco execuções, com o mesmo modelo, o mesmo prompt e as mesmas regras — muda só a
recuperação.

O resultado: a busca puramente vetorial acerta nove de quinze, sessenta por cento. O híbrido e o
plano Cypher acertam quatorze de quinze, noventa e três por cento.

Mas o número que interessa está por grupo. No grupo multi-hop, o vetor puro acerta um de cinco; o
híbrido, quatro; o plano, cinco. É exatamente onde a arquitetura promete. Em três dessas perguntas o
vetor recebeu trechos sobre o assunto e mesmo assim não respondeu, porque um trecho isolado não liga
dois conceitos.

E o número que eu considero o mais importante: abstenção de cinco em cinco nos três modos. Nenhum
modo respondeu pergunta fora do corpus. Além disso, em quarenta e três respostas, nenhuma citação
não verificada: duas falhas de verificação viraram recusa, não resposta errada.

Os tempos médios ficaram em sessenta e cinco, setenta e um e cinquenta e um segundos.

## Slide 11 · O que este resultado não prova — 0:45

Quatro limites, e prefiro dizer antes de ser perguntado.

A cobertura de relações: vinte e três relações condicionam tudo, e as perguntas da avaliação usam
praticamente todos os caminhos disponíveis.

Circularidade parcial: os documentos esperados vêm das evidências do grafo, o que favorece por
construção os modos que usam o grafo.

A amostra: quinze perguntas, uma execução por célula. E revisão humana: nenhuma etapa teve revisão
independente dos fatos extraídos.

O que mais mudaria o resultado, na sequência, é ampliar a extração de relações e trocar o gabarito
derivado do grafo por anotação de uma pessoa.

## Slide 12 · Demonstração — 2:00

[Voltar para a interface, execução salva já aberta.]

Vou fazer a pergunta ao vivo. [Digitar] *"Quais relações ligam integridade referencial a chaves
estrangeiras?"* — modo híbrido.

Enquanto roda: são de um a três minutos, porque o modelo é local, em uma GPU de quatro gigabytes.
[Se demorar, abrir a execução salva.] Esta execução salva é a mesma pergunta, no mesmo sistema.

[Apontar] Aqui a resposta. Cada afirmação com o marcador E1, que aponta para a citação aqui embaixo —
o trecho original em inglês, do capítulo 9. Aqui o painel que explica o nível: cobertura de cem por
cento, dois de dois afirmações com evidência, um documento só — por isso médio, não alto. E aqui o
subgrafo: integridade referencial governa chave estrangeira, e autojunção é uma forma de junção.

Agora a segunda pergunta, que é a mais importante. [Digitar] *"receita de bolo de cenoura."*

[Apontar] A tela diz que a pergunta não corresponde a nada no grafo e oferece termos que existem.
Não é erro: é a funcionalidade. O sistema prefere não responder a inventar — e é essa a diferença
entre um assistente que ajuda e um que atrapalha.

Obrigado. Fico à disposição.

---

## Se o tempo apertar (corte para 8 min)

Corte o slide 4 inteiro e diga em uma frase, no slide 3: "a arquitetura tem quatro pilares, e as
duas decisões nossas são: o modelo não escreve a consulta e o nível não vem do modelo." Depois
pule do 5 para o 6. Economia: 55 segundos. Se precisar de mais, encurte a demo para uma pergunta e
deixe a recusa como frase final.

## Se sobrar tempo (o que acrescentar)

- A história do defeito que corrigimos: dois tetos de saltos diferentes, três e quatro, no mesmo
  sistema — e como medimos que a correção não mudava nenhum resultado.
- O índice de texto que existia e ninguém usava, e que agora alimenta a sugestão de conceitos.

## Cola de números

| O quê | Número |
|---|---|
| Documentos / trechos | 9 / 59 (31 texto + 28 figuras) |
| Conceitos / relações | 93 / 23 (16 nos três arquivos principais) |
| Menções trecho→conceito | 134 |
| Índices | 6 (4 propriedade, 1 texto, 1 vetor 384d) |
| Casos de ataque no guard | 38 (32 recusas obrigatórias) |
| Perguntas da avaliação | 15 (5 / 5 / 5) · 45 execuções |
| Acerto: vetor / híbrido / grafo | 60% / 93% / 93% |
| Multi-hop | 1/5 · 4/5 · 5/5 |
| Abstenção fora do corpus | 5/5 nos três modos |
| Citações não verificadas | 0 em 43 respostas |
| Tempo médio por resposta | 65 s · 71 s · 51 s |
