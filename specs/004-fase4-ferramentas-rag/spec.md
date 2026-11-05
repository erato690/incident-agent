# Feature Specification: Fase 4 — ferramentas externas, consulta SQL e RAG

**Feature Branch**: `004-fase4-ferramentas-rag` (sem branch git dedicada; trabalho local em `main`)

**Created**: 2026-11-05

**Status**: Clarified (decisões D1 a D8 do Rafael em 2026-11-05; ver `research.md`)

**Input**: Pedido do conductor (2026-11-05): "Fase 4: SOMENTE preparar decisões. Escopo já
combinado: sugestão de ação (o agente só sugere, nunca executa em produção); ferramenta de stats
do banco (lê stats do banco do incident-shop; contrato 1.1.0 do shop); memória semântica (fatos
de produto/regras com fonte, data, validade; pesquisa externa e, quando não achar, pergunta ao
usuário); casos que devem passar a acertar: rate_limit e banco_lento (nomear o reindex). Use só
peças ensinadas na aula." Somam-se os itens da rubrica da Fase 4 (seção 4 do notebook).

## Contexto

Seção 4 do notebook único (constitution, princípio X). As Fases 1 a 3 entregaram a barreira de
entrada, o Investigador (agente ReAct com ferramentas só leitura) e a memória de curto e longo
prazo (episódica completa; semântica só como interface `FatoSemantico`). Hoje o Investigador
acerta a causa em 6 a 7 de 8 cenários. Dois cenários ficam de fora:

- **`rate_limit`** (pagamentos-api): os logs já trazem "PagaFácil respondeu 429 Too Many
  Requests (X-RateLimit-Limit: 100/min)", mas o agente responde "picos de carga" e não cita o
  limite do provedor externo.
- **`banco_lento_com_deploy`** (pedidos-api): o agente aponta o banco e não culpa o deploy
  distrator, mas não nomeia a reindexação (`REINDEX TABLE estoque` no db-principal), embora o
  texto apareça num WARN do estoque-worker.

A Fase 4 dá ao agente três capacidades novas, todas só leitura:

1. **Consulta SQL (text-to-query)** sobre uma base SQLite, com recusa de comando de escrita.
2. **Recuperação (RAG) sobre um índice vetorial FAISS existente** de runbooks e documentação,
   com uma falha de recuperação diagnosticada e corrigida.
3. **Memória semântica em uso (a wiki)**: o agente consulta fatos sobre produtos e serviços;
   quando falta ou venceu, busca na documentação; se não achar, pergunta ao usuário e grava a
   resposta só depois de confirmada.

E fecha dois comportamentos: **sugestão de ação** (o agente propõe a correção com base no
runbook e deixa claro que não executou nada) e **estatísticas do banco** para chegar na
reindexação.

Itens da rubrica atendidos (constitution, princípio IX):

| Item da rubrica (Fase 4) | Onde nesta spec |
|---|---|
| Ferramentas hardcoded × semânticas | US4, FR-014 |
| APIs conforme o tipo de uso (API web e API interna) | US4, FR-015 |
| Text-to-query | US2, FR-004 a FR-007 |
| Agente de recuperação sobre índice FAISS existente | US3, FR-008 a FR-010 |
| Falha de recuperação diagnosticada e corrigida (transformação da pergunta) | US3, FR-011 |

## Clarifications

### Session 2026-11-05

- Q: Escopo? → A (Rafael, D1): rubrica completa + escopo combinado.
- Q: De onde vêm as estatísticas do banco? → A (D2): rota `GET /estatisticas_banco` do
  incident-shop (contrato 1.1.0) + ferramenta fixa; dados gravados enquanto a rota não sai.
- Q: O que vai na SQLite? → A (D3): histórico de incidentes, serviços e deploys.
- Q: Camadas da recusa de escrita? → A (D4): lista de proibidos + início `SELECT` (aula 6).
- Q: Corpus e ferramenta de recuperação? → A (D5): 8 a 12 runbooks e documentos próprios;
  ferramenta com scores; `create_retriever_tool` só na comparação.
- Q: Pesquisa externa da memória semântica? → A (D6): busca na documentação indexada; grava o
  fato com fonte, data e validade.
- Q: Pergunta ao usuário? → A (D7): na própria resposta; grava só após confirmação
  (intenção `confirmar_fato`), com trava.
- Q: Sugestão de ação? → A (D8): ferramenta semântica `sugerir_acao`; ações "não executada".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Os dois cenários que faltavam passam a acertar (Priority: P1)

O engenheiro investiga `rate_limit` e `banco_lento_com_deploy`. No primeiro, o agente diz que o
tráfego passou do limite de 100 requisições por minuto do PagaFácil (HTTP 429), citando o fato
semântico com fonte e data. No segundo, nomeia a reindexação da tabela `estoque` no
db-principal como causa, citando as estatísticas do banco, e descarta o deploy v3.2.1.

**Why this priority**: é o ganho de comportamento combinado com o Rafael; fecha 8/8.

**Independent Test**: bateria com a chave nos dois cenários; testes sem chave com fakes que
verificam a ferramenta chamada e a evidência citada.

**Acceptance Scenarios**:

1. **Given** o cenário `rate_limit`, **When** o agente investiga, **Then** a hipótese principal
   cita o limite de 100/min do PagaFácil e o 429, e a evidência inclui o fato semântico (fonte,
   data de verificação).
2. **Given** o cenário `banco_lento_com_deploy`, **When** o agente investiga, **Then** a hipótese
   principal nomeia a reindexação da tabela `estoque`, com evidência das estatísticas do banco,
   e o deploy aparece como descartado.
3. **Given** qualquer dos 8 cenários, **When** o agente termina, **Then** a resposta traz ações
   sugeridas marcadas como "sugestão, não executada".

### User Story 2 - Pergunta em linguagem natural vira consulta SQL segura (Priority: P2)

O engenheiro pergunta "quantos incidentes o pedidos-api teve neste mês e qual a causa mais
comum?".
O agente gera um `SELECT`, executa na base SQLite e responde com o SQL e o resultado.

**Independent Test**: pergunta, SQL gerado e resultado impressos; `DROP TABLE` recusado antes
de chegar ao banco; testes sem chave.

**Acceptance Scenarios**:

1. **Given** uma pergunta de contagem, **When** o agente consulta, **Then** a trajetória mostra o
   SQL `SELECT` e a resposta usa o número devolvido.
2. **Given** uma tentativa de `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE` ou
   `REPLACE`, **When** a ferramenta recebe a consulta, **Then** recusa com mensagem e o banco não
   muda.

### User Story 3 - Agente de recuperação sobre runbooks, com falha corrigida (Priority: P2)

O engenheiro diz "o site está travando". A busca crua não acha o runbook de "pool de conexões
esgotado". O notebook mostra os trechos e scores antes; o agente reescreve a pergunta em termos
técnicos e a segunda busca acha o runbook certo; o notebook mostra trechos e scores depois.

**Independent Test**: índice FAISS construído por script e carregado com `load_local`; scores
antes e depois impressos; teste sem chave com embedding falso.

**Acceptance Scenarios**:

1. **Given** o índice salvo em disco, **When** a seção 4 roda, **Then** carrega o índice sem
   reconstruí-lo.
2. **Given** a pergunta crua, **When** busca, **Then** o runbook certo não está entre os k
   primeiros (falha registrada); **Given** a pergunta reescrita, **Then** está em primeiro.
3. **Given** score acima do limiar de cobertura, **When** a ferramenta responde, **Then** declara
   que a base não cobre o assunto, sem inventar.

### User Story 4 - Explicação dos tipos de ferramenta e de API (Priority: P3)

O professor lê a seção 4 e vê a tabela das ferramentas por tipo (hardcoded, semântica) e das
APIs por uso (API web pública do GitHub, API interna do incident-shop), com uma chamada de cada.

**Independent Test**: tabelas e chamadas impressas no notebook.

### User Story 5 - Memória semântica: buscar, perguntar e gravar (Priority: P2)

Numa investigação, o agente precisa do limite de um provedor. Consulta a wiki; se o fato falta
ou venceu, busca na documentação indexada; se achar, grava o fato com fonte "documentacao",
data e validade. Se não achar, pergunta ao usuário; quando o usuário responde e confirma, grava
com fonte "usuario".

**Independent Test**: três caminhos impressos (fato válido, fato da documentação, fato do
usuário); testes sem chave.

**Acceptance Scenarios**:

1. **Given** fato válido na wiki, **When** consulta, **Then** usa o fato sem nova busca.
2. **Given** fato vencido ou ausente e documento indexado, **When** consulta, **Then** grava fato
   novo com fonte e data e o cita.
3. **Given** nada na documentação, **When** consulta, **Then** a resposta pergunta ao usuário e
   nada é gravado até a confirmação.
4. **Given** texto da documentação com instrução embutida, **When** gravado, **Then** é tratado
   como dado (camada 4 dos guardrails) e mascarado.

### Edge Cases

- Consulta SQL com `SELECT` seguido de `;` e outro comando: recusada.
- Pergunta SQL fora do esquema: o agente diz que a base não tem o dado.
- Índice FAISS ausente em disco: erro claro com o comando do script que o constrói.
- Estatísticas do banco indisponíveis (shop fora do ar, se D2 = rota): modo gravado.
- Fato semântico com `valido_ate` no passado: tratado como vencido e refeito.
- Usuário responde a pergunta do agente com dado ambíguo: não grava; pergunta de novo.
- Pedido para "executar o reindex" ou "reiniciar o serviço": o agente recusa executar e repete a
  sugestão.

## Requirements *(mandatory)*

### Functional Requirements

**Comportamento**

- **FR-001**: O agente MUST nomear a reindexação da tabela `estoque` como causa em
  `banco_lento_com_deploy`, com evidência de uma ferramenta de estatísticas do banco (rota
  `GET /estatisticas_banco`, D2).
- **FR-002**: O agente MUST citar o limite de 100/min do PagaFácil em `rate_limit`, com evidência
  do fato semântico.
- **FR-003**: O agente MUST sugerir ações (ação, motivo, risco, runbook de origem) e MUST NOT
  executar nenhuma; nenhuma ferramenta de escrita em sistema externo (forma conforme D8).

**Consulta SQL**

- **FR-004**: Ferramenta `@tool` só leitura sobre SQLite, entrada Pydantic "apenas SELECT",
  esquema no prompt, com exemplos de consultas (padrão ensinado).
- **FR-005**: Recusa por lista negra (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`,
  `TRUNCATE`, `REPLACE`) e por exigir início `SELECT`; camadas extras conforme D4.
- **FR-006**: Base SQLite gerada por script a partir de `dados_dummy/` (conteúdo conforme D3),
  versionada no repositório e reconstruível.
- **FR-007**: A saída mostra o SQL gerado e o resultado.

**Recuperação**

- **FR-008**: Corpus de runbooks e documentação em texto (conforme D5), dividido com
  `RecursiveCharacterTextSplitter`, embeddings `text-embedding-3-small`.
- **FR-009**: Índice FAISS construído por script (`save_local`) e carregado no notebook com
  `load_local(..., allow_dangerous_deserialization=True)`; o índice é arquivo próprio do projeto.
- **FR-010**: Ferramenta de recuperação com `similarity_search_with_score`, `k`, filtro por
  metadado e limiar de "sem cobertura" (forma conforme D5).
- **FR-011**: Falha diagnosticada e corrigida: pergunta crua × reescrita pelo agente (transformação
  da pergunta por prompt e argumento da ferramenta), trechos e scores antes e depois.

**Memória semântica**

- **FR-012**: Ferramentas para consultar e gravar fatos semânticos sobre `MemoriaLongoPrazo`
  (interface da Fase 3); gravação só com trava, como `gravar_episodio`.
- **FR-013**: Ordem: wiki → documentação (conforme D6) → pergunta ao usuário (conforme D7).
  Texto externo é dado, nunca instrução; mascarado antes de gravar.

**Explicação**

- **FR-014**: Tabela das ferramentas por tipo (hardcoded, semântica) com uma de cada em uso.
- **FR-015**: Tabela das APIs por uso (API web do GitHub, API interna do incident-shop).

**Transversais**

- **FR-016**: Prompts em inglês terminando em "Always answer in Brazilian Portuguese."
- **FR-017**: Testes sem chave e sem rede, com fakes; ruff sem avisos.
- **FR-018**: Seção 4 independente das anteriores; bateria e conversas com a chave no notebook.

### Key Entities

- **Ação sugerida**: ação, motivo, risco, runbook de origem, "não executada".
- **Estatística de tabela**: serviço/banco, tabela, varreduras sequenciais × por índice,
  reindexação em andamento, último `ANALYZE`, inchaço do índice.
- **Runbook**: título, serviço, tipo de falha, passos; metadados para filtro.
- **Fato semântico** (já existe): assunto, fato, fonte, verificado_em, valido_ate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Bateria com a chave: causa certa em 8/8 cenários, incluindo `rate_limit` e
  `banco_lento_com_deploy` (reindexação nomeada).
- **SC-002**: 100% das tentativas de escrita no SQL recusadas antes do banco.
- **SC-003**: Falha de recuperação mostrada: runbook certo fora dos k primeiros antes, em
  primeiro depois.
- **SC-004**: Os três caminhos da memória semântica impressos; nenhum fato gravado sem fonte e
  data.
- **SC-005**: Toda resposta final com ação sugerida marcada como não executada; zero ferramentas
  de escrita.
- **SC-006**: Seção 4 em até 300 s com a chave; testes sem chave passando.

## Assumptions

- Peças da aula usadas: `@tool` + Pydantic + `sqlite3` com lista negra; `FAISS` com
  `save_local`/`load_local`; `similarity_search_with_score`; `RecursiveCharacterTextSplitter`;
  `OpenAIEmbeddings`; `create_retriever_tool` (citado); `InMemoryVectorStore` da Fase 3.
- Sem equivalente na aula (só com decisão do Rafael): `PRAGMA query_only`, busca na web,
  `interrupt`/pergunta ao humano por mecanismo, `create_sql_agent`, `MultiQueryRetriever`/HyDE.
- O PagaFácil é fictício; não existe documentação dele na web.
- Fora do escopo: auditor, agente único com `AgentExecutor`, Streamlit, LangSmith (Fase 5).
