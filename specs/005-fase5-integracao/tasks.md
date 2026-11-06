# Tasks: Fase 5

TDD. Comandos: `.venv/bin/pytest -q`, `.venv/bin/ruff check . && .venv/bin/ruff format --check .`
(nunca `uv run`). Prompts em inglês, terminando em "Always answer in Brazilian Portuguese.".
Textos para o leitor em português, sem citar "aula N".

## Phase 1: Foundational

- [ ] T101 `agente/schemas.py`:
  - `PassoTrajetoria.observacao: str | None` (texto mascarado, até 2000 caracteres), preenchido em
    `agente/trajetoria.py` (`on_tool_end`);
  - `RespostaTurno.auditoria: Auditoria | None` e `RespostaTurno.aviso: str | None`.
  - Testes.

## Phase 2: US2 Auditor (P1) [P com T104 e T105]

- [ ] T102 [P] [US2] `agente/auditor.py`:
  - modelos: `Afirmacao` (texto, chave `Literal["versao","horario","numero","tabela","servico","outro"]`, valor), `ListaAfirmacoes`, `ChecagemFato` (afirmacao, status `Literal["confirmada","contraditoria","nao_verificada"]`, fonte), `VereditoCoerencia` (veredito `Literal["apoia","refuta","neutro"]`, e_coerente, falacias `list[Literal[...]]` (FR-006), justificativa), `Auditoria` (aprovada, checagens, coerencia, motivos, erro);
  - `checar_fatos(afirmacoes, trajetoria)`, determinística: valor normalizado presente nas observações significa "confirmada"; para versão e horário, outro valor do mesmo tipo presente significa "contraditoria"; senão "nao_verificada";
  - `montar_auditor(llm)`: extração `with_structured_output(ListaAfirmacoes)`, checagem e coerência `with_structured_output(VereditoCoerencia)` com as observações e a análise;
  - reprova se houver contraditória, se e_coerente for falso ou se houver falácia diferente de "nenhuma"; mais de 50% de não verificadas também reprova;
  - erro do modelo gera `Auditoria(aprovada=False, erro=...)` com o motivo "não auditada";
  - prompts em inglês;
  - testes `tests/test_auditor.py`: certa aprovada, número inventado reprovado, deploy posterior reprovado.
- [ ] T103 [US2] `agente/pipeline.py`: `montar_pipeline(..., auditor=None)`. Com auditor, toda resposta de rota "investigacao" passa por ele: grava `RespostaTurno.auditoria` e, se reprovada, `aviso` "Resposta reprovada pelo auditor: <motivos>". Sem auditor, nada muda. Testes.

## Phase 3: US3 Post-mortem (P3) [P]

- [ ] T104 [P] [US3] `agente/postmortem.py`:
  - `DadosPostMortem` (Pydantic) e `gerar_postmortem(dados) -> str` (template: resumo; impacto e severidade; linha do tempo; causa raiz e evidência; ações sugeridas (não executadas); próximos passos; sem episódio não gera: decisão de 2026-11-06 no `research.md`);
  - `salvar_postmortem(dados, pasta)`;
  - no pipeline, com memória, `gerar_relatorio` monta o post-mortem a partir da última análise da sessão (histórico ou `estado["ultima_analise"]`) e do episódio confirmado do incidente; o texto fixo antigo sai.
  - Testes `tests/test_postmortem.py`.

## Phase 4: US1 Agente integrado (P1)

- [ ] T105 [P] [US1] `agente/registro.py`: `RegistroTurno` (session_id, pergunta, rota, resposta resumida, trajetória, auditoria, duracao_ms, criado_em) e `Registro` (adicionar, listar, salvar JSON). Testes.
- [ ] T106 [US1] `agente/integrado.py`:
  - `montar_agente_integrado(llm, cenario, memoria, indice, banco, embeddings_relevancia..., auditor=True)`: ferramentas das Fases 2 a 4 + `consultar_sql`, Investigador `max_passos` 12, pipeline com memória e auditor, `montar_conversa` (Fase 3) por `session_id`;
  - devolve um objeto com `turno(sessao, mensagem) -> RespostaTurno` que também grava o `RegistroTurno`;
  - `montar_agente_classico(llm, ferramentas)`: `create_openai_tools_agent` + `AgentExecutor` (langchain_classic), `return_intermediate_steps=True`.
  - Regra no prompt do Investigador para `consultar_sql` (perguntas sobre histórico, contagens).
  - Testes com fakes.

## Phase 5: US5 LangSmith (P2)

- [ ] T107 [US5] `agente/avaliacao.py`:
  - `exemplos_dataset()` (8 cenários de `dados_dummy/fase4_mensagens.json`: inputs mensagem e cenário; outputs palavras_causa, ferramentas_esperadas, causa_esperada);
  - avaliadores no formato do `langsmith.evaluate` (`def avaliador(run, example) -> {"key","score","comment"}`, ou `outputs`/`reference_outputs`; conferir a assinatura na versão instalada): `causa_certa`, `trajetoria_ferramentas`, `auditor_aprovou`;
  - `alvo(fabrica)` (inputs para outputs serializáveis: causa principal, ferramentas, auditoria).
  - `scripts/avaliar_langsmith.py` (`--enviar` exige a flag explícita; sem ela, roda os avaliadores localmente e imprime as métricas).
  - Testes `tests/test_avaliacao.py` sem rede.

## Phase 6: US4 Streamlit (P2)

- [ ] T108 [US4] `app/app.py`:
  - aba "Uso": cenário (selectbox), nova sessão, `st.chat_input` e `st.chat_message`, análise formatada com aviso do auditor e ações sugeridas;
  - aba "Análise": tabela do `Registro` e detalhe por turno;
  - `st.session_state` guarda o agente e a sessão; sem chave, mostra aviso.
  - `requirements-app.txt`, `Dockerfile` (porta `${PORT:-8501}`), `docker-compose.yml`.
  - Teste de import e funções puras (formatação) em `tests/test_app.py`.

## Phase 7: Notebook e entrega

- [ ] T109 Seção 5 do notebook (independente):
  - 5.1 arquitetura final;
  - 5.2 auditor (certa aprovada, errada reprovada);
  - 5.3 agente integrado numa conversa de 4 ou mais turnos (sintoma, SQL, confirmação, post-mortem);
  - 5.4 clássico `create_openai_tools_agent` + `AgentExecutor` × `create_agent`;
  - 5.5 `RunnableWithMessageHistory`;
  - 5.6 Streamlit (prints);
  - 5.7 LangSmith (métricas e análise);
  - 5.8 rubrica para a célula.
  - Seção 5 em até 300 s.
- [ ] T110 Renomear as seções pela capacidade, ajustar as referências e criar a seção 0 (diagrama de contexto, agente final num cenário, índice geral da rubrica).
- [ ] T111 Diagramas (`scripts/gerar_diagramas.py`): componentes da Fase 4 e arquitetura final.
- [ ] T112 Execução completa com a chave; mesclar as saídas; `docs/projeto.html`; README; varredura de segredos; commit local.
- [ ] T113 `relatório técnico (fora do repositório)` e o PDF `PDF do relatório (fora do repositório)` (problema, arquitetura, decisões por fase, avaliação, limitações, evidências, processo com o spec-kit, IAs usadas).
