# Tasks: Fase 4 — ferramentas externas, consulta SQL e RAG

Fonte: [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md),
[contracts/estatisticas_banco.md](contracts/estatisticas_banco.md). TDD: teste primeiro (falha),
depois o código. Comandos: `.venv/bin/pytest -q`, `.venv/bin/ruff check . && .venv/bin/ruff format --check .`
(nunca `uv run`). Prompts em inglês terminando em "Always answer in Brazilian Portuguese."
Código, docstrings e textos para leitor em português, sem citar "aula N", siglas por extenso.

## Phase 1: Setup

- [X] T001 Instalar `faiss-cpu`, `langchain-community`, `langchain-text-splitters` na `.venv` e acrescentar em `requirements.txt`

## Phase 2: Foundational (bloqueia as histórias)

- [ ] T002 Em `agente/schemas.py`: `AcaoSugerida`, `ListaAcoes` (data-model.md); `AnaliseIncidente.acoes_sugeridas` (default `[]`); `Intencao` + `confirmar_fato`; `ContextoTurno.acoes_sugeridas` e `fato_gravado`; `RespostaTurno.fato`. Testes em `tests/test_schemas.py` (status fixo "sugerida (não executada)"; Fases 1–3 continuam válidas)

## Phase 3: US2 — consulta SQL (P2) [P com US3 e T010]

- [ ] T003 [P] [US2] `scripts/construir_sqlite.py` gera `dados/incidentes.db` determinístico (tabelas servicos, deploys, incidentes; data-model.md) e `tests/test_construir_sqlite.py`
- [ ] T004 [P] [US2] `agente/sql.py`: `validar_consulta` (início SELECT; lista negra DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, REPLACE; recusa `;` seguido de outro comando), `BancoSQL.executar` (colunas + até 50 linhas), `ESQUEMA` (texto para o prompt), `montar_ferramenta_sql` (`@tool consultar_sql` com entrada Pydantic "Apenas SELECT"), `montar_agente_sql(llm)` (`create_agent`, prompt PTCF com esquema e exemplos de consultas). Testes `tests/test_sql.py` (recusa 7 comandos e `SELECT 1; DROP`, banco inalterado, modelo falso)

## Phase 4: US3 — recuperação FAISS (P2) [P]

- [ ] T005 [P] [US3] Corpus `dados/documentos/*.md`: 8 runbooks (pool de conexões esgotado, reindexação/bloqueio de tabela, limite de requisições de dependência externa, gateway externo indisponível, certificado TLS expirado, vazamento de memória/OOMKilled, variável de ambiente faltando, deploy com bug/NullPointerException) + 2 documentos (limites da API do PagaFácil: 100 req/min por conta, 429 com Retry-After; política de manutenção do db-principal). Cabeçalho `titulo/tipo/servico/assunto`. O runbook de pool NÃO usa as palavras "travando"/"site" (falha de recuperação demonstrável)
- [ ] T006 [P] [US3] `agente/recuperacao.py`: `carregar_documentos` (cabeçalho -> metadados), `dividir` (`RecursiveCharacterTextSplitter`), `construir_indice(embeddings, destino)` (`FAISS.from_documents` + `save_local`), `carregar_indice(origem, embeddings)` (`FAISS.load_local(..., allow_dangerous_deserialization=True)`, erro claro se ausente), `buscar_com_score(indice, consulta, k=3, filtro=None)`, `LIMIAR_SEM_COBERTURA` (distância L2; calibrar com a chave), `montar_ferramenta_recuperacao(indice)` (`@tool buscar_documentacao(consulta, tipo=None)` com trechos, título e score; "sem cobertura" acima do limiar), `montar_agente_recuperacao(llm, indice)` (prompt manda reescrever a pergunta em termos técnicos antes de buscar), `ferramenta_retriever_comparacao(indice)` (`create_retriever_tool`). Silenciar o `DeprecationWarning` do `langchain-community` só aqui. `scripts/construir_indice.py`. Testes `tests/test_recuperacao.py` com `DeterministicFakeEmbedding` e índice em `tmp_path`

## Phase 5: US1 — estatísticas do banco e cenários que faltavam (P1)

- [ ] T007 [P] [US1] `agente/loja.py`: `FonteLoja.estatisticas_banco(servico)` (ao vivo `GET /estatisticas_banco?cenario&servico`; gravada lê `dados["estatisticas_banco"]` filtrando por serviço; ausente -> `tabelas: []`), `resumir_estatisticas`. Docstring do módulo cita 1.1.0. Fixtures nos 8 `dados_dummy/cenarios/*.json` (chave `estatisticas_banco`, contrato; `REINDEX TABLE estoque` só em `banco_lento_com_deploy`). Testes `tests/test_estatisticas_banco.py` (MockTransport e gravado)
- [ ] T008 [US1] `agente/acoes.py`: `SISTEMA_ACAO` (inglês), `montar_ferramenta_acao(llm, indice)` (`@tool sugerir_acao(diagnostico, servico)`: busca runbook (tipo=runbook), LLM `with_structured_output(ListaAcoes)`, força status, guarda no `ContextoTurno.acoes_sugeridas`, devolve texto "SUGESTÃO, NÃO EXECUTADA"). Testes `tests/test_acoes.py`
- [ ] T009 [US1] `agente/ferramentas.py`: `consultar_estatisticas_banco(servico)`; `montar_ferramentas(..., indice=None, llm_acao=None, estatisticas=False)` acrescenta `consultar_estatisticas_banco`, `buscar_documentacao`, `consultar_wiki`, `sugerir_acao` conforme o que foi passado (sem nada: lista igual à Fase 3). Testes `tests/test_ferramentas.py`

## Phase 6: US5 — memória semântica (P2)

- [ ] T010 [US5] `agente/ferramentas.py`: `consultar_wiki(assunto, pergunta)`: 1) `memoria.consultar_fatos_semanticos` válido -> usa; 2) senão `buscar_com_score` tipo=documentacao abaixo do limiar -> `registrar_fato_semantico` (fonte documentacao, verificado_em=agora, valido_ate=agora+90 dias, texto mascarado) e cita; 3) senão "NÃO ENCONTRADO: pergunte ao usuário: <pergunta>". `gravar_fato(assunto, fato)` com trava (intenção `confirmar_fato`, fonte usuario). Testes `tests/test_wiki.py` (três caminhos; vencido refeito; instrução embutida mascarada/tratada como dado; trava recusa)
- [ ] T011 [US5] `agente/prompts.py`: NLU reconhece `confirmar_fato` (exemplo few-shot). `agente/pipeline.py`: `confirmar_fato` -> Registrador com `gravar_fato` (`SISTEMA_REGISTRO_FATO`), resposta rota "memoria" com `fato`; ações do contexto copiadas para `analise.acoes_sugeridas` por código. Testes `tests/test_pipeline_fase4.py`

## Phase 7: Prompt do Investigador (US1)

- [ ] T012 [US1] `agente/agente_react.py`: regras condicionais às ferramentas (como `REGRA_MEMORIA`): banco (sinal de banco -> `consultar_estatisticas_banco`; manutenção em andamento é causa raiz, cite-a), dependência externa (429/503 de provedor -> `consultar_wiki(provedor, ...)`, compare limite × `requisicoes`), wiki (fato não encontrado -> pergunta em `dado_que_falta`), ação (no fim, `sugerir_acao` uma vez com a hipótese principal). `max_passos` 12 na seção 4. Testes em `tests/test_agente_react.py`

## Phase 8: US4 + notebook (P3)

- [ ] T013 [US1] `agente/bateria.py`: `causa_certa(mensagem, resposta)` por `palavras_causa`; coluna na tabela. `dados_dummy/fase4_mensagens.json` (8 investigações com `palavras_causa`, 2 SQL, 1 fato ausente, 1 confirmar_fato, 1 pedido de execução) e `fase4_conversas.json`. Testes `tests/test_bateria.py`
- [ ] T014 Construir com a chave: `scripts/construir_indice.py` (índice em `dados/indice_faiss/`); calibrar `LIMIAR_SEM_COBERTURA` e a pergunta crua da falha de recuperação com scores reais (registrar em research.md)
- [ ] T015 Notebook `projeto.ipynb`, seção 4 (independente): 4.1 tipos de ferramenta e de API (tabelas + uma chamada de cada); 4.2 text-to-query (pergunta, SQL, resultado; DROP recusado); 4.3 agente de recuperação sobre FAISS existente (`load_local`), `create_retriever_tool` na comparação; 4.4 falha de recuperação (trechos e scores antes e depois); 4.5 memória semântica (três caminhos + confirmar_fato); 4.6 estatísticas do banco e `banco_lento`; 4.7 `rate_limit`; 4.8 ação sugerida e recusa de execução; 4.9 bateria e conversas; 4.10 rubrica -> célula. Seção 4 ≤ 300 s
- [ ] T016 Execução completa com a chave; mesclar saídas; diagrama (`scripts/gerar_diagramas.py`), `docs/projeto.html`, README; research.md com números; varredura de segredos; commit local sem atribuição

## Dependências

T002 antes de T008–T013. T003/T004, T005/T006 e T007 em paralelo (arquivos distintos). T009
depende de T006–T008; T010 de T006 e T009; T011 de T010; T012 de T009–T010; T013–T016 no fim.
