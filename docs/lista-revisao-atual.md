# Lista atual para conferência humana

Os códigos C01–C88 preservam a numeração enviada no chat. C89–C93 são os cinco conceitos acrescentados. As 26 modificações e os cinco conceitos novos da entrega anterior foram aprovados pelo usuário; não se presume aprovação de cada fato preexistente. Consulte data/review/user-approval-source-check-v1.json. As descrições são resumos em português, não citações literais. As evidências originais estão nos três arquivos indicados em data/release/current.json.

| Item | ID persistido | Conceito | Resumo | Trechos |
|---|---|---|---|---|
| C01 | C_aggregate_function | função agregadora | Função que calcula um resultado a partir de múltiplas linhas de entrada. | D08_C001 |
| C02 | C_aggregation | agregação | Cálculo agregado sobre as entradas de uma função; a opção FILTER pode selecionar as entradas de uma agregação específica. | D08_C002 |
| C03 | C_alternate_key | chave alternativa | Chave candidata que não foi escolhida como chave primária. | D02_C007 |
| C04 | C_and | operador AND | Operador booleano utilizado em condições de seleção e também em condições de junção nos exemplos da fonte. | D06_C001, D07_C002 |
| C05 | C_armstrong_s_axioms | axiomas de Armstrong | Regras de inferência usadas para obter dependências funcionais. | D04_C003 |
| C06 | C_as | cláusula AS | Palavra usada para atribuir outro nome a uma coluna de saída nos exemplos. | D06_C001, D07_C002 |
| C07 | C_atomic_value | valor atômico | Valor considerado indivisível no contexto do modelo relacional. | D09_C003 |
| C08 | C_attribute | atributo | Unidade principal de armazenamento descrita em D09 como coluna, campo ou atributo, que contém componentes básicos dos dados. | D09_C001, D09_C003 |
| C09 | C_avg | função AVG | Função de média citada pela fonte entre as funções agregadoras. | D08_C001 |
| C10 | C_boolean_expression | expressão booleana | Expressão de valor lógico utilizada para selecionar linhas na cláusula WHERE. | D06_C001 |
| C11 | C_business_rule | regra de negócio | Regra obtida dos usuários durante o levantamento de requisitos e utilizada para determinar cardinalidade e conectividade. | D03_C003, D03_C005 |
| C12 | C_candidate_key | chave candidata | Chave simples ou composta que é única e mínima. | D02_C007 |
| C13 | C_cardinality | cardinalidade | Expressa números mínimo e máximo de ocorrências associadas a uma ocorrência de entidade relacionada. | D03_C005 |
| C14 | C_characteristic_entity | entidade característica | Entidade que fornece informação adicional sobre outra tabela, na terminologia da fonte. | D02_C007 |
| C15 | C_composite_attribute | atributo composto | Atributo formado por uma hierarquia de atributos. | D02_C007 |
| C16 | C_composite_key | chave composta | Chave formada por dois ou mais atributos e que deve ser mínima, conforme o glossário da fonte. | D02_C007 |
| C17 | C_connectivity | conectividade | Classificação da conexão entre tabelas como um para um ou um para muitos na notação da fonte. | D03_C005 |
| C18 | C_constraint | restrição | Regra que exige do SGBD a verificação da semântica dos dados. | D03_C001, D03_C005 |
| C19 | C_count | função COUNT | Função agregadora de contagem apresentada nos exemplos com count(*). | D08_C001, D08_C002 |
| C20 | C_data | dados | Menção contextual aos dados recuperados por SELECT; o trecho utilizado não oferece uma definição geral do conceito de dado. | D06_C001 |
| C21 | C_data_element | elemento de dado | Fato que representa informação do mundo real. | D01_C002 |
| C22 | C_database | banco de dados | Coleção compartilhada de dados relacionados usada para apoiar atividades de uma organização. | D01_C002 |
| C23 | C_database_administrator | administrador de banco de dados | Administrador de banco de dados, identificado pela sigla DBA; a evidência de glossário apenas expande a sigla. | D04_C003 |
| C24 | C_database_system | sistema de banco de dados | Expressão de categoria utilizada pela fonte para classificar um SGBD relacional; o trecho não apresenta uma definição geral de sistema de banco de dados. | D03_C005 |
| C25 | C_dbms | sistema gerenciador de banco de dados | Conjunto de programas para criar e manter bancos de dados e controlar seu acesso. | D01_C002 |
| C26 | C_degree | grau de uma tabela | Número de atributos de uma tabela. | D09_C003 |
| C27 | C_dependent_entity | entidade dependente | Entidade cujo significado depende de outras tabelas, conforme a fonte. | D02_C007 |
| C28 | C_derived_attribute | atributo derivado | Atributo cujo valor é calculado a partir de outros atributos. | D02_C007 |
| C29 | C_determinant | determinante | Elemento apresentado no lado esquerdo do diagrama de dependência funcional. | D04_C003 |
| C30 | C_distinct | modificador DISTINCT | Modificador usado para remover linhas duplicadas do resultado, sem garantir ordenação por si só. | D06_C001 |
| C31 | C_domain | domínio | Conjunto de valores aceitáveis para uma coluna. | D09_C003 |
| C32 | C_entity | entidade | Objeto com existência independente que pode ser distinguido de outros objetos. | D02_C007 |
| C33 | C_entity_integrity | integridade de entidade | Regra conceitual segundo a qual toda tabela deve ter chave primária e nenhum componente dessa chave pode ser nulo, conforme a fonte. | D03_C001, D03_C005 |
| C34 | C_entity_relationship_data_model | modelo de dados entidade-relacionamento | Modelo representado por diagramas entidade-relacionamento para modelagem de dados. | D02_C007 |
| C35 | C_entity_set | conjunto de entidades | Coleção de entidades de um tipo em um dado instante. | D02_C007 |
| C36 | C_entity_type | tipo de entidade | Tipo que reúne entidades semelhantes, na caracterização do glossário. | D02_C007 |
| C37 | C_fd_dependent | dependente de uma dependência funcional | Elemento apresentado no lado direito do diagrama de dependência funcional. | D04_C003 |
| C38 | C_filter | opção FILTER | Opção que seleciona entradas de uma função agregadora específica, sem filtrar necessariamente as demais. | D08_C002 |
| C39 | C_first_normal_form | primeira forma normal | Forma em que as interseções de linhas e colunas têm valores únicos, sem grupos repetidos, na apresentação didática da fonte. | D05_C004 |
| C40 | C_foreign_key | chave estrangeira | Chave que estabelece uma referência entre tabelas; a fonte a apresenta como atributo que referencia a chave primária de outra tabela e admite a possibilidade de nulo. | D02_C007 |
| C41 | C_from | cláusula FROM | Cláusula que indica as fontes de dados nos exemplos de consulta. | D06_C001, D07_C001, D07_C002, D08_C001, D08_C002 |
| C42 | C_functional_dependency | dependência funcional | Relação em que, para cada ocorrência válida de X, o valor de X determina unicamente o valor de Y, representada por X → Y. | D04_C001, D04_C003, D05_C002 |
| C43 | C_group_by | cláusula GROUP BY | Cláusula usada nos exemplos para formar grupos sobre os quais agregações são calculadas. | D08_C001, D08_C002 |
| C44 | C_grouped_row | linha do resultado agrupado | Expressão contextual para uma linha do resultado agrupado, sobre a qual HAVING pode aplicar um filtro. | D08_C001 |
| C45 | C_having | cláusula HAVING | Cláusula que seleciona grupos após o agrupamento e a agregação, tipicamente com condições sobre agregados; a fonte ressalva que também pode ser escrita sem funções agregadoras. | D08_C001, D08_C002 |
| C46 | C_identifying_relationship | relacionamento identificador | Relacionamento em que a PK contém a FK, representado por linha contínua na fonte e também chamado de relacionamento forte. | D02_C005, D03_C005 |
| C47 | C_independent_entity | entidade independente | Entidade apresentada como base sobre a qual outras tabelas são construídas. | D02_C007 |
| C48 | C_inner_join | junção interna | Junção interna que combina linhas correspondentes e ignora linhas sem correspondência, conforme o exemplo da fonte. | D07_C001, D07_C002 |
| C49 | C_integrity_constraint | restrição de integridade | Declaração lógica que limita valores e formatos permitidos para os dados; a fonte apresenta integridade de entidade e integridade referencial entre seus tipos. | D03_C001, D03_C005 |
| C50 | C_join | junção | Operação que combina linhas de tabelas conforme uma expressão. | D07_C001, D07_C002 |
| C51 | C_key | chave | Atributo ou grupo de atributos cujos valores identificam uma entidade em um conjunto. | D02_C007 |
| C52 | C_left_outer_join | junção externa à esquerda | Junção que preserva cada linha da tabela à esquerda ao menos uma vez; quando não há correspondência à direita, as colunas desse lado recebem valores nulos. | D07_C002 |
| C53 | C_like | operador LIKE | Operador de correspondência de padrões citado na explicação dos exemplos. | D08_C002 |
| C54 | C_mandatory_relationship | relacionamento obrigatório | Relacionamento em que uma ocorrência exige uma ocorrência correspondente. | D03_C005 |
| C55 | C_max | função MAX | Função que calcula um máximo nos exemplos de agregação. | D08_C001, D08_C002 |
| C56 | C_min | função MIN | Função de mínimo citada pela fonte entre as funções agregadoras. | D08_C001 |
| C57 | C_multivalued_attribute | atributo multivalorado | Atributo que pode ter um conjunto de valores para cada entidade. | D02_C007 |
| C58 | C_non_identifying_relationship | relacionamento não identificador | Relacionamento em que a FK não integra a PK, representado por linha pontilhada na fonte e também chamado de relacionamento fraco. | D02_C005, D03_C005 |
| C59 | C_non_normalized_table | tabela não normalizada | Tabela caracterizada pela presença de redundância de dados, na terminologia do glossário da fonte. | D04_C003 |
| C60 | C_normalization | normalização | Ramo da teoria relacional que fornece subsídios ao projeto: caracteriza o nível de redundância e oferece mecanismos de transformação de esquemas para removê-la. | D05_C001, D05_C004 |
| C61 | C_not | operador NOT | Operador booleano permitido nas condições de seleção da fonte. | D06_C001 |
| C62 | C_null | nulo | Símbolo para informação desconhecida ou não aplicável, distinto de zero e de texto vazio. | D02_C007 |
| C63 | C_optional_relationship | relacionamento opcional | Relacionamento que permite ausência de uma ocorrência correspondente, conforme as alternativas descritas na fonte. | D03_C005 |
| C64 | C_or | operador OR | Operador booleano permitido nas condições de seleção da fonte. | D06_C001 |
| C65 | C_order_by | cláusula ORDER BY | Cláusula usada para ordenar os resultados nos exemplos. | D06_C001 |
| C66 | C_orphan_record | registro órfão | Registro cujo valor de FK não é encontrado na entidade correspondente, segundo a definição da fonte. | D03_C005 |
| C67 | C_outer_join | junção externa | Forma de junção que representa ausência de correspondência com valores nulos, conforme os exemplos. | D07_C002 |
| C68 | C_postgresql | PostgreSQL | Sistema de banco de dados citado na documentação-base como oferecendo funções agregadoras. | D08_C001 |
| C69 | C_primary_key | chave primária | Chave candidata escolhida pelo projetista para identificar unicamente as tuplas de uma tabela; não pode ser nula e é indicada por sublinhado no modelo ER apresentado na fonte. | D02_C004, D03_C001 |
| C70 | C_referential_integrity | integridade referencial | Regra de validade das referências; a fonte descreve correspondência com a chave referenciada ou nulo. | D03_C005 |
| C71 | C_relation | relação do modelo relacional | Subconjunto de um produto cartesiano de domínios; D09 também o apresenta como termo técnico equivalente a tabela ou arquivo. | D09_C001, D09_C003 |
| C72 | C_relational_dbms | sistema gerenciador de banco de dados relacional | Sistema de banco de dados baseado no modelo relacional. | D03_C005 |
| C73 | C_relational_model | modelo relacional | Modelo introduzido por E. F. Codd em 1970 que descreve o mundo como uma coleção de relações, ou tabelas, inter-relacionadas. | D03_C001, D09_C001 |
| C74 | C_relationship | relacionamento | Associação ou interação entre entidades para conectar informações relacionadas. | D02_C007 |
| C75 | C_relationship_strength | força do relacionamento | Característica ligada à maneira como a chave primária da entidade relacionada é definida. | D02_C007 |
| C76 | C_relationship_type | tipo de relacionamento | Tipo de relacionamento entre tabelas em um DER, identificado na fonte como identificador ou não identificador. | D03_C005 |
| C77 | C_row | linha | Ocorrência em uma tabela relacional; registro e tupla são tratados como aliases no contexto deste glossário. | D07_C001, D09_C003 |
| C78 | C_select | consulta SELECT | Consulta usada para recuperar dados de tabelas. | D06_C001, D07_C001, D07_C002, D08_C001, D08_C002 |
| C79 | C_self_join | autojunção | Forma de junção em que uma tabela é combinada com ela própria. | D07_C002 |
| C80 | C_semantic_rule | regra semântica | Regra de negócio aplicada ao banco de dados. | D05_C004 |
| C81 | C_simple_attribute | atributo simples | Atributo proveniente de um domínio de valores atômicos; D02 também o chama de single-valued attribute. | D02_C003, D02_C007 |
| C82 | C_stored_attribute | atributo armazenado | Atributo salvo fisicamente no banco de dados. | D02_C007 |
| C83 | C_structured_query_language | linguagem de consulta estruturada | Linguagem padrão de acesso a bancos de dados identificada pela sigla SQL, conforme o glossário da fonte. | D09_C003 |
| C84 | C_sum | função SUM | Função de soma citada pela fonte entre as funções agregadoras. | D08_C001 |
| C85 | C_table | tabela | Estrutura que armazena dados em linhas e colunas; D09 também utiliza tabela, relação e arquivo como termos equivalentes no contexto do capítulo. | D01_C002, D09_C001, D09_C003 |
| C86 | C_third_normal_form | terceira forma normal | Na apresentação didática da fonte, a relação está em 2FN e tem removidas as dependências transitivas: um atributo não chave não pode depender funcionalmente de outro não chave. | D05_C002, D05_C004 |
| C87 | C_unary_relationship | relacionamento unário | Relacionamento entre ocorrências do mesmo conjunto de entidades. | D02_C007 |
| C88 | C_where | cláusula WHERE | Cláusula que seleciona linhas por uma condição; a fonte explica sua aplicação antes da agregação. | D06_C001, D07_C001, D08_C001, D08_C002 |
| C89 | C_n_ary_relationship | relacionamento n-ário | No recorte de mapeamento de D02, relacionamento com mais de duas entidades participantes, representado por uma nova relação. | D02_C007 |
| C90 | C_ternary_relationship | relacionamento ternário | Relacionamento entre três entidades participantes, representadas por tabelas no exemplo de D02; não se impõe que todos os lados sejam sempre muitos. | D02_C007 |
| C91 | C_fd_decomposition | decomposição de dependências funcionais | Regra segundo a qual X → YZ implica X → Y e X → Z; é apresentada como inversa da regra da união. | D04_C003 |
| C92 | C_fd_union | união de dependências funcionais | Regra segundo a qual X → Y e X → Z implicam X → YZ. | D04_C002 |
| C93 | C_second_normal_form | segunda forma normal | Na apresentação didática de D05, exige 1FN; uma PK simples atende à condição descrita, e, se a PK é composta, cada atributo não chave deve depender de toda a PK, não apenas de parte dela. | D05_C002 |

As 16 relações da revisão anterior permanecem inalteradas. P01 (esquema/modelo ER), P03 (simples/monovalorado) e P08 (arquivo/relação) foram fechados como remissões contextuais em docs/fechamento-pendencias.md, sem alterar esta lista ou criar equivalências globais. As propostas SQL X01–X05 continuam fora da base; inconsistências F01–F04 continuam sinalizadas.
