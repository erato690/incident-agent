# Research: Fase 4 — ferramentas externas, consulta SQL e RAG

Rodada única de decisões (2026-11-05), preparada antes de codar. O Jev (jev-1.14.0) deu opinião,
com a confiança entre parênteses. **Rafael decidiu em 2026-11-05: todas as opções recomendadas**
(ver "Decisões do Rafael" no fim).

## Mapeamento contra o material da aula

| Componente | Peça da aula | Evidência | Situação |
|---|---|---|---|
| Text-to-SQL | `@tool` própria com `sqlite3`, `Field("Apenas SELECT")`, lista negra, esquema no prompt, exemplos | aula 6 (transcrição 50:57 e 51:45; notebook, célula 14) | Ensinado |
| `SQLDatabaseToolkit` | só citado | aula 7 (41:55) | Citado |
| `PRAGMA query_only`, `create_sql_agent`, `create_sql_query_chain` | — | — | Sem equivalente |
| FAISS existente | `FAISS.save_local` e `load_local(..., allow_dangerous_deserialization=True)` | aula 4 (notebook, célula 35) | Ensinado |
| Ferramenta de recuperação | `@tool` com `similarity_search_with_score`, `k`, filtro de metadado, limiar "sem cobertura" | aula 6 (notebook, células 21 e 23) | Ensinado |
| `create_retriever_tool` | devolve só texto, sem score | aula 7 (40:39) | Ensinado |
| Falha de recuperação | transformação da pergunta por prompt e argumento da ferramenta | aula 6 (1:03:49, 1:10:30, 1:28:14) | Ensinado |
| `MultiQueryRetriever`, HyDE | — | — | Sem equivalente |
| Hardcoded × semântica | hardcoded é determinística; semântica tem um LLM no motor | aula 6 (21:26, 26:39, 37:45) | Ensinado |
| API interna × externa | API interna do service mesh; API externa de clima | aula 6 (36:22); aula 3 | Ensinado, sem esses nomes |
| Busca na web | — | nenhuma ocorrência | Sem equivalente |
| Pergunta ao humano (`interrupt`, `HumanInputRun`) | só no prompt ("pergunte de novo") e no campo "dado faltante" do NLU | aula 5 (1:31:09) | Sem mecanismo |
| Sugestão sem execução | restrição de capacidade e humano no laço (só conceito) | aula 6 (42:16, 45:34) | Conceito |
| Estatísticas do banco | `@tool` genérica | — | Sem desvio |

O texto oficial da rubrica não está no material. Só há o resumo em `estudo/jev/avaliar.py`:
"ferramentas hardcoded vs semanticas, tipos de API, text-to-query, agente de recuperacao FAISS,
diagnostico de falha de recuperacao + query transformation".

## Fatos levantados

- **`rate_limit`:** os logs gravados trazem o 429 do PagaFácil com `X-RateLimit-Limit: 100/min`
  (150 ocorrências em `dados_dummy/cenarios/rate_limit.json`). O PagaFácil é fictício e não tem
  documentação na web.
- **`banco_lento_com_deploy`:** os logs gravados trazem o WARN "REINDEX TABLE estoque" do
  estoque-worker. O agente não usa esse texto como causa.
- **incident-shop:**
  - Contrato 1.0.0 (`api/main.py:16`), sem nada planejado para 1.1.0.
  - Sem SQLite e sem estatísticas de banco.
  - A política do contrato diz que rota nova é acréscimo compatível e sobe a versão para 1.1.0.
- **incident-agent:** sem SQLite, sem FAISS e sem runbooks. `FatoSemantico` e
  `consultar_fatos_semanticos` já existem, mas nenhuma ferramenta do agente os usa.

## Decisões pendentes (nível 3)

### D1 — Escopo
- **A (rec.; Jev A 0,68):** rubrica completa mais todo o escopo combinado.
- **B:** só o escopo combinado. Perde text-to-query, FAISS e a falha de recuperação.
- **C:** como A, mas sem a pergunta ao usuário e sem a validade dos fatos.

### D2 — Estatísticas do banco
- **A (rec.; Jev A 0,67):** rota `GET /estatisticas_banco` no incident-shop (contrato 1.1.0),
  `@tool` fixa no agente e `dados_dummy` regravado. É o que foi combinado e mostra a "API
  interna". Exige sessão no shop, push e redeploy no Railway. Custa cerca de +3 h.
- **B:** tabela no estilo `pg_stat_user_tables` na SQLite local, consultada pelo text-to-query.
  Não muda o shop e uma peça cobre dois itens. Afasta-se do combinado.
- **C:** só uma regra no prompt para ler o REINDEX nos logs. Não entrega a ferramenta.

### D3 — Conteúdo da SQLite
- **B (rec. se D2 = A):** histórico de incidentes, serviços e deploys, para perguntas como
  "quantos incidentes o pedidos-api teve e qual a causa mais comum?". Não repete a rota.
- **A (Jev A 0,38):** snapshot do db-principal por cenário (pedidos, estoque e estatísticas).
  Natural se D2 = B.
- **C:** as duas bases (+1 h).

### D4 — Recusa de escrita no SQL
- **B (rec.; Jev B 0,88):** só o que a aula ensina: lista negra, início `SELECT` e recusa de `;`
  com um segundo comando.
- **A:** como B, mais conexão `mode=ro` e `PRAGMA query_only`. É defesa extra, mas vai além da
  aula.

### D5 — Corpus e ferramenta de recuperação
- **A (rec.; Jev A 0,74):**
  - Corpus de 8 a 12 runbooks e páginas de documentação em markdown, escritos para o projeto.
    Inclui a documentação fictícia do PagaFácil e o runbook de reindexação.
  - `@tool` com `similarity_search_with_score` (aula 6), que mostra os scores.
  - `create_retriever_tool` aparece só na comparação.
- **B:** mesmo corpus, com `create_retriever_tool` como ferramenta principal. Sem score no agente.
- **C:** indexar episódios passados em vez de runbooks.

### D6 — "Pesquisa externa" da memória semântica (busca na web não foi ensinada)
- **A (rec.; Jev A 0,51 × B 0,48):** a pesquisa é uma busca na documentação indexada no FAISS.
  Se achar, grava o fato com fonte "documentacao", data e validade. Usa só peças da aula e roda
  sem rede.
- **B:** `@tool` HTTP (padrão da aula 3) que baixa a página do PagaFácil publicada no repositório
  público do shop. É mais "externa", mas exige push no shop e precisa de modo gravado.
- **C:** Tavily ou DuckDuckGo. Não foi ensinado, traz dependência e chave nova, e o resultado não
  é determinístico.

### D7 — Pergunta ao usuário (sem `interrupt` ensinado)
- **A (rec.; Jev A 1,00):** a resposta traz a pergunta (padrão do "dado faltante"). No turno
  seguinte, o dado vira fato com fonte "usuario" só depois de confirmado, por uma ferramenta de
  gravação com trava, como `gravar_episodio`.
- **B:** `interrupt` do LangGraph (não ensinado).
- **C:** ferramenta que bloqueia esperando entrada. Não foi ensinada e não roda no notebook
  automático.

### D8 — Sugestão de ação
- **A (rec.; Jev A 0,73):**
  - Ferramenta semântica `sugerir_acao`: um LLM dentro da ferramenta, que é o exemplo de
    ferramenta semântica da aula 6.
  - Recebe o diagnóstico e o runbook.
  - Devolve `acoes_sugeridas` (ação, motivo, risco, runbook) marcadas "não executada".
  - Muda o schema da saída.
- **B:** só o campo no schema, preenchido pelo Investigador.
- **C:** execução simulada com aprovação humana (não ensinada).

## Mudança no contrato do incident-shop (só se D2 = A, ou se D6 = B)

- **D2 = A:**
  - Rota `GET /estatisticas_banco?cenario=&servico=`.
  - Cada linha da resposta: tabela, varreduras sequenciais, varreduras por índice, reindexação
    em andamento, último `ANALYZE` e inchaço do índice em %.
  - `VERSAO_CONTRATO` passa a "1.1.0". É retrocompatível.
  - Arquivos tocados: `api/modelos.py`, `api/fontes/__init__.py`, `simulada.py`, `servicos.py`,
    `api/cenarios.py`, `api/main.py`, `docs/contrato-api.md`, `openapi.json`, `README.md`,
    `scripts/gravar_dados_dummy.py`.
  - Testes: `test_contrato.py`, `test_saude_cenarios.py`, `test_gravacao.py`, mais testes novos.
  - Precisa de uma sessão no incident-shop, de commit e push no repositório do shop e de redeploy
    no Railway. As três são ações externas e pedem o Rafael.
  - O agente roda sem o shop no ar, pelo modo gravado.
- **D6 = B:** acrescenta só a página `docs/pagafacil-limites.md` no repositório do shop, sem rota
  nova.

## Estimativa (horas de trabalho do agente, com execução real)

| Fase 4 | h |
|---|---|
| plan, tasks e análise | 1,0 |
| SQLite, ferramenta SQL e testes | 2,0 |
| corpus, script do índice FAISS, ferramenta de recuperação e falha corrigida | 3,0 |
| memória semântica (consultar, documentação, perguntar, gravar) | 2,5 |
| sugestão de ação (ferramenta semântica e schema) | 1,5 |
| estatísticas: rota no shop + ferramenta (D2 = A) / SQLite (D2 = B) | 3,0 / 1,0 |
| ajuste do prompt para `rate_limit` e `banco_lento` | 1,5 |
| notebook (seção 4), execuções com a chave, página e research | 3,0 |
| **Total** | **17,5 (D2 = A) / 15,5 (D2 = B)** |

| Fase 5 | h |
|---|---|
| renomear seções e seção 0 | 1,5 |
| auditor (extração, checagem de fatos, inferência e falácias) | 4,0 |
| agente único `create_openai_tools_agent` + `AgentExecutor` + `RunnableWithMessageHistory` | 3,0 |
| Streamlit com duas telas | 4,0 |
| LangSmith: dataset e avaliadores (precisa de `LANGSMITH_API_KEY`) | 3,0 |
| notebook, execuções com a chave e página | 2,0 |
| relatório PDF | 4,0 |
| vídeo (Rafael) | 1,0 |
| **Total** | **22,5** |

Candidatos a corte, do menor para o maior impacto na nota:

| Corte | Horas poupadas | Efeito |
|---|---|---|
| D2 = B | 2 | — |
| D6 sem gravação da documentação | 1 | — |
| Streamlit só com a tela de uso | 2 | — |
| Auditor só com checagem de fatos (sem falácias) | 1,5 | — |
| D1 = C | 1,5 | Afeta o escopo combinado |

## Decisões do Rafael (2026-11-05)

| # | Decisão | Motivo |
|---|---|---|
| D1 | A: rubrica completa (text-to-query, FAISS, falha de recuperação, tipos de ferramenta e de API) + escopo combinado | A rubrica cobra os itens; o combinado fecha os dois cenários que faltavam |
| D2 | A: rota `GET /estatisticas_banco` no incident-shop (1.1.0) + ferramenta fixa `consultar_estatisticas_banco` | É o combinado e mostra a API interna; sessão própria do incident-shop faz a rota (contrato em `contracts/estatisticas_banco.md`); até lá, dados gravados |
| D3 | B: SQLite com histórico de incidentes, serviços e deploys | Não repete a rota de estatísticas; dá perguntas gerenciais reais ao text-to-query |
| D4 | B: lista de proibidos + início `SELECT` (aula 6) | Só peça ensinada |
| D5 | A: 8 a 12 runbooks e documentos próprios; ferramenta com `similarity_search_with_score`; `create_retriever_tool` só na comparação | Mostra os scores, que o diagnóstico da falha exige |
| D6 | A: "pesquisa externa" = busca na documentação indexada; achou, grava fato com fonte, data e validade | Peças da aula, sem rede, determinístico |
| D7 | A: pergunta na própria resposta; grava só após confirmação, com trava | Padrão do "dado faltante"; `interrupt` não foi ensinado |
| D8 | A: ferramenta semântica `sugerir_acao`; ações "não executada" | Exemplo de ferramenta semântica da aula 6 |

Ordem de corte se faltar tempo (Rafael): Streamlit só com a tela de uso; verificador sem
falácias; D6 sem gravar o fato. Não cortar LangSmith, relatório nem notebook.

## Decisões de nível 1 e 2 (seguem sem perguntar)

- **Dependências:** `faiss-cpu`, `langchain-community` e `langchain-text-splitters` entram,
  porque a D5 exige FAISS (`langchain_community.vectorstores.FAISS`, como na aula 4). O
  `langchain-community` emite `DeprecationWarning` ("`langchain-community` is being sunset and is
  no longer actively maintained"). Mesmo tratamento da D9b da Fase 3: registrar e silenciar só no
  módulo que importa o FAISS.
- **Confirmação de fato (D7):** intenção nova `confirmar_fato` no NLU (o engenheiro informa e
  confirma um fato de produto ou serviço). Só nela a ferramenta `gravar_fato` grava (trava como a
  de `gravar_episodio`). Fonte "usuario", validade padrão de 90 dias.
- **Validade de fato da documentação (D6):** 90 dias a partir da consulta.
- **Ações sugeridas (D8):** `sugerir_acao` guarda as ações no contexto do turno e o pipeline as
  copia para `AnaliseIncidente.acoes_sugeridas` por código (como a citação do SC-002), sem
  depender do modelo repetir o JSON.
- **Agentes da seção 4:** agente de consulta SQL e agente de recuperação (`create_agent`) mostrados
  isolados; o Investigador ganha as ferramentas novas. A integração num agente único fica na
  Fase 5.
- **Acerto da causa na bateria:** item com `palavras_causa`; a causa é certa quando a hipótese
  principal contém uma das palavras (ex.: "reindex", "100").

## Calibração da recuperação com embeddings reais (2026-11-05)

Índice `dados/indice_faiss/` (10 documentos, 13 pedaços, `text-embedding-3-small`), distância
L2 (menor = mais parecido), k = 3:

| Consulta | 1º (score) | Runbook de pool |
|---|---|---|
| "o site está travando" | gateway externo indisponível (1,136) | 3º (1,321) |
| "pool de conexões esgotado, timeout ao obter conexão do banco no pico de tráfego" | pool de conexões esgotado (0,555) | 1º |
| "limite de requisições da API do PagaFácil" | Limites da API do PagaFácil (0,366) | — |
| "lock wait e statement timeout na tabela estoque" | reindexação e bloqueio de tabela (0,980) | — |
| "como fazer bolo de cenoura" | (1,585) | sem cobertura |
| "configurar ingress do kubernetes com TLS" | certificado TLS expirado (1,189) | sem cobertura |

- Falha de recuperação: com k = 2, a pergunta crua "o site está travando" não traz o runbook de
  pool, e o 1º colocado é o errado, com score abaixo do limiar (falso positivo confiante). A
  pergunta reescrita em termos técnicos põe o runbook certo em 1º, com 0,555.
- `LIMIAR_SEM_COBERTURA` fica em 1,15, o valor que a aula usa: fora do domínio, a distância vai de
  1,19 a 1,59.
