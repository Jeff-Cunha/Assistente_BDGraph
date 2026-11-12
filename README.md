# Assistente_BDGraph

Projeto acadêmico da disciplina **Tendências em Ciência da Computação**, desenvolvido por uma equipe de seis integrantes.

O objetivo é construir um assistente de perguntas e respostas sobre bancos de dados utilizando **GraphRAG/KAG**, **Neo4j** e **modelos de linguagem (LLMs)**, com respostas fundamentadas em documentos e visualização das evidências utilizadas.

> Projeto em desenvolvimento. As funcionalidades descritas como previstas ainda serão implementadas.

## Objetivo

Investigar como a combinação de recuperação textual e grafos de conhecimento pode apoiar respostas rastreáveis e reduzir afirmações sem sustentação documental.

O sistema deverá conectar informações distribuídas entre documentos, permitindo responder perguntas que exijam percorrer múltiplos relacionamentos.

## Escopo da primeira versão

- **Fundamentos:** banco de dados, SGBD, modelo relacional, tabelas, linhas e colunas.
- **Modelagem relacional:** entidades, atributos, relacionamentos, cardinalidades, chaves e integridade referencial.
- **Normalização:** dependências funcionais e formas normais até a 3FN.
- **SQL básico:** SELECT, FROM, WHERE, JOIN, GROUP BY, HAVING e funções de agregação.

## Funcionalidades previstas

- Extração automática de entidades e relações a partir dos documentos.
- Resolução de entidades para tratar nomes equivalentes e evitar duplicidades.
- Armazenamento do conhecimento no Neo4j.
- Configuração de restrições de unicidade e índices de propriedades, texto e vetores.
- Recuperação híbrida, combinando busca vetorial e consultas Cypher.
- Geração e validação de consultas Cypher com apoio de LLM.
- Travessia de dois ou mais relacionamentos e aplicação de algoritmo de grafo.
- Geração de respostas com referências às evidências recuperadas.
- Tratamento de perguntas sem evidências suficientes.
- Interface com visualização interativa do subgrafo, fontes, consulta Cypher e indicador de confiança com significado documentado.

## Arquitetura prevista

```mermaid
flowchart TD
    A[Documentos] --> B[Limpeza e divisão em trechos]
    B --> C[Extração de entidades e relações]
    C --> D[Resolução de entidades]
    D --> E[Neo4j e índices]

    P[Pergunta do usuário] --> F[Recuperação híbrida]
    E --> F
    F --> G[Evidências e caminhos do grafo]
    G --> H[Geração de resposta com LLM]
    H --> I[Interface, fontes e visualização do subgrafo]
```

## Base documental

O corpus inicial contém **9 documentos**, organizados em **31 trechos textuais**, provenientes de:

- **Database Design — 2nd Edition**, disponibilizado pelo BCcampus.
- **Documentação oficial do PostgreSQL 18**.

Os textos permanecem em inglês. A aplicação deverá permitir perguntas e respostas em português, com tratamento de termos equivalentes entre os idiomas.

A preparação do corpus preserva os documentos originais, exemplos SQL, metadados de origem e avisos de atribuição. Foram preparados **28 suplementos de figuras**, separados dos 31 trechos originais, totalizando **59 trechos**. Duas transcrições permanecem parciais, com incertezas registradas.

## Estado atual

- [x] Definição do tema e do escopo inicial.
- [x] Seleção e coleta dos nove documentos.
- [x] Limpeza e organização dos textos.
- [x] Divisão em trechos com identificação das fontes.
- [x] Verificação de integridade dos arquivos do corpus.
- [x] Complementação textual das figuras essenciais, com limitações documentadas.
- [x] Definição inicial do esquema do grafo e dos formatos de integração.
- [x] Primeira versão de extração local, resolução de nomes e revisão rastreável.
- [x] Revisão de 26 resumos/contextos e inclusão de cinco conceitos, com aprovação do usuário registrada.
- [x] Remissões contextuais de esquema ER, monovalorado e arquivo, sem fusão automática de conceitos.
- [ ] Ampliação da cobertura de relações e avaliação humana independente.
- [ ] Configuração e ingestão no Neo4j.
- [ ] Recuperação híbrida e consultas multi-hop.
- [ ] Integração com LLM.
- [ ] Interface e visualização.
- [ ] Avaliação, artigo técnico e apresentação.

## Organização do trabalho

| Frente | Responsabilidade |
|---|---|
| 1. Dataset e extração | Preparação documental, extração de entidades e relações e tratamento de duplicidades. |
| 2. Modelagem e Neo4j | Esquema do grafo, ingestão, restrições e índices. |
| 3. Recuperação | Busca híbrida, travessias multi-hop e algoritmo de grafo. |
| 4. LLM | Geração e validação de Cypher e respostas fundamentadas. |
| 5. Interface | Interação com o usuário e visualização das evidências. |
| 6. Avaliação e integração | Conjunto de avaliação, testes integrados e reprodução do sistema. |

Todos os integrantes contribuirão com documentação, testes, artigo e apresentação.

## Tecnologias

**Definidas pelo projeto:**
- Neo4j e Cypher.
- Modelo de linguagem.
- Modelo de embeddings.

Os scripts de preparação e extração usam Python. Ollama e Qwen3 8B foram usados para a extração local. O adaptador Gemini continua disponível, mas as tentativas iniciais não produziram extração validada. A escolha final dos modelos, embeddings e interface permanece em aberto.

## Instalação e execução

Para conferir a amostra manual (PowerShell 7):

```powershell
pwsh -NoProfile -File scripts/validate-extraction.ps1
```

Para testar a consolidação (Python 3.10 ou superior):

```powershell
python -m pip install -r requirements-extraction.txt
python -m unittest discover -s tests -p "test_*.py" -v
```

A amostra inicial contém 12 conceitos e 9 relações e permanece identificada como manual. As saídas atuais de regras e LLM foram executadas e revisadas separadamente; a extração ainda não é exaustiva.

- [Entrega para a parte 2 e critérios de ingestão](docs/entrega-parte1-para-parte2.md)
- [Contrato de dados](docs/contrato-extracao.md)
- [Modelo do grafo e ingestão no Neo4j](docs/modelo-grafo.md)
- [O que a parte 2 entrega para as partes 3, 4, 5 e 6](docs/handoff-parte2.md)
- [Preparação e qualidade do corpus](corpus/README.md)
- [Consolidação das extrações](docs/consolidacao-extracao.md)
- [Configuração da API Gemini](docs/configuracao-gemini.md)
- [ZIP da entrega inicial para a parte 2](outputs/parte1-para-parte2.zip)

No estado atual, ainda não há um assistente executável. O corpus e sua documentação já estão incluídos. O Neo4j e a aplicação ainda precisam ser implementados.

Senhas, credenciais do Neo4j e chaves de API não devem ser versionadas. As configurações necessárias serão exemplificadas em um arquivo `.env.example`, sem valores secretos.

## Base revisada para integração

A entrega atual contém **93 conceitos únicos e 16 relações semânticas únicas**, deduplicando IDs/triplas dos três arquivos indicados em [data/release/current.json](data/release/current.json). Não inclui a amostra manual inicial opcional nesses totais.

| Origem | Arquivo principal | Conteúdo |
|---|---|---|
| Regras e curadoria | [Base por regras](data/extraction/rule-knowledge-union-v2/extraction.json) | 79 conceitos e 5 relações |
| LLM e curadoria | [Base derivada do modelo](data/extraction/model-knowledge-union-v3/extraction.json) | 20 conceitos e 11 relações |
| Curadoria manual assistida por IA | [Conceitos acrescentados na revisão](data/extraction/manual-source-review-v1/extraction.json) | 5 conceitos e nenhuma nova relação |

As 26 correções de resumos/contextos e os cinco conceitos acrescentados foram [aprovados pelo usuário](data/review/user-approval-source-check-v1.json), com vínculo aos hashes da entrega. Essa aprovação não equivale a revisão independente de todos os conceitos/relações ou avaliação do sistema final. Os cinco conceitos novos são n-ário, ternário, decomposição de dependências, união de dependências e 2FN.

Os conceitos compartilhados devem ser atualizados por ID, reunindo aliases e evidências e preservando os métodos. Importar somente os três primary_files do índice atual. Candidatos, versões históricas, controles sintéticos e respostas rejeitadas **não são fatos adicionais aprovados**.

O [registro de remissões contextuais](data/normalization/contextual-aliases-v1.json) é auxiliar à busca, não um quarto arquivo de fatos. Esquema ER/modelo ER e monovalorado/simples estão restritos a D02; arquivo/relação está restrito a D09. O resolvedor exige contexto e nunca autoriza fusão de nós. A exceção de FD em D05_C002 exige revisão do contexto. Essa etapa foi conferida por Codex, sem aprovação humana posterior presumida.

- [Guia atualizado para a pessoa 2](docs/entrega-parte1-atualizada.md)
- [Resumos corrigidos e evidências](docs/revisao-fontes-2026-11-09.md)
- [Lista dos 93 conceitos para conferência](docs/lista-revisao-atual.md)
- [Fechamento das três pendências](docs/fechamento-pendencias.md)
- [D05 para leitura, com tabelas em Markdown](corpus/reading/D05.md)
- [Resultados e limitações de SQL](docs/cobertura-sql.md)
- [Execução local no computador principal](docs/modelo-local-principal.md)
- [Pacote atual completo e auditoria](outputs/entrega-parte1-pendencias-concluidas.zip)

corpus/reading contém cópias para leitura: seis tabelas de D05 foram formatadas em Markdown e o quadro explicativo de D08 foi mantido sem cabeçalho inventado. A extração continua usando corpus/processed e corpus/chunks, cujos bytes foram preservados. As cópias de leitura não criam novos documentos/chunks nem substituem evidências.

Use o esquema deste repositório, compatível com 0.1.0, 0.1.1 e 0.1.2. Os tipos SQL adicionais exigem 0.1.2. Para validar os dados entregues, não é necessário ter Ollama ou chave de API:

```powershell
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/rule-knowledge-union-v2/extraction.json
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/model-knowledge-union-v3/extraction.json
pwsh -NoProfile -File scripts/validate-extraction.ps1 -ExtractionPath data/extraction/manual-source-review-v1/extraction.json
python scripts/resolve-contextual-alias.py --term "file" --chunk D09_C003
```

Os **65 testes passaram**. Os hashes, IDs e evidências literais dos três arquivos foram conferidos. Permanecem problemas nas fontes, duas transcrições parciais e cobertura limitada de relações. Não há comprovação experimental de redução de alucinações nem ingestão no Neo4j concluída.

## Avaliação planejada

A avaliação utilizará perguntas com respostas e evidências esperadas, incluindo:

- Perguntas conceituais simples.
- Perguntas que exigem múltiplos relacionamentos.
- Perguntas sem resposta na base documental.

Serão analisadas a correção das respostas, a recuperação das evidências e a rastreabilidade. Está prevista uma comparação com recuperação exclusivamente vetorial.

## Entregas

- Código-fonte e instruções de execução.
- Sistema funcional com interface e visualização do grafo.
- Testes e resultados de avaliação.
- Artigo técnico em formato SBC ou IEEE.
- Apresentação e demonstração do sistema.

## Fontes e atribuições

- [Database Design — 2nd Edition](https://opentextbc.ca/dbdesign01/)
- [Tutorial do PostgreSQL 18](https://www.postgresql.org/docs/18/tutorial.html)

Os materiais do corpus mantêm suas respectivas licenças e atribuições, incluindo avisos específicos de conteúdo de terceiros. Essas condições devem acompanhar sua redistribuição.

A licença do código desenvolvido pela equipe ainda será definida.
