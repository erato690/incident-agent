# Tasks: Fase 3 — memória de curto e longo prazo

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/memoria.md](contracts/memoria.md)

**Tests**: TDD (constitution e pedido do Rafael): cada teste é escrito antes e falha antes da
implementação. Testes sem chave e sem rede (modelo falso, `DeterministicFakeEmbedding`, relógio
injetado).

## Phase 1: Setup

- [X] T001 Conferir no `.venv` as APIs usadas (`StateGraph`, `MemorySaver`, `InMemoryStore` com
  `index`, `RemoveMessage`, `OpenAIEmbeddings`, `DeterministicFakeEmbedding`,
  `ConversationBufferMemory`/`ConversationChain` do `langchain-classic`) e anotar desvios em
  `specs/003-fase3-memoria/research.md`

## Phase 2: Foundational

- [X] T002 Testes dos schemas novos em `tests/test_memoria.py`: `Episodio` (`origem` ∈
  {"agente", "engenheiro"}, `historico_causas: list[CausaHistorica]` vazia por padrão), `FatoSemantico` (`fonte` ∈
  {"documentacao", "usuario", "incidente"}, `valido_ate` opcional), `Sessao`, `CausaConfirmada`,
  `RespostaTurno` com rota `"memoria"`, `episodio` e `episodio_anterior`
- [X] T003 Schemas em `agente/schemas.py` (episódica e semântica separadas) e `agente/memoria.py`
- [X] T004 Testes de `MemoriaLongoPrazo` em `tests/test_memoria.py`: registrar e consultar
  episódio; mesma causa não duplica e devolve `None`; causa diferente atualiza `causa`, move a anterior para `historico_causas` (causa, data,
  quem confirmou) e devolve o episódio anterior; depois da troca, a busca pela causa antiga não
  acha o episódio por ela (só a vigente é indexada) e a busca pela nova acha; filtro por serviço; decaimento (`peso_tempo = 0.5 ** (dias /
  meia_vida_dias)`) coloca o recente na frente com similaridade igual; namespaces separados
  (consulta episódica nunca devolve fato semântico); fato semântico vencido por `valido_ate`;
  `salvar` e `carregar` em JSON (arquivo temporário) preservam tudo; texto com segredo é
  guardado mascarado
- [X] T005 `MemoriaLongoPrazo` e `embeddings_padrao()` em `agente/memoria.py` conforme
  `contracts/memoria.md`

## Phase 3: User Story 1 — causa confirmada vira episódio (P1)

**Independent test**: conversa A confirma a causa; conversa B, outro identificador, pergunta "já
aconteceu antes?" e a ferramenta devolve o episódio de A.

- [X] T006 [P] [US1] Testes em `tests/test_ferramenta_memoria.py`: `montar_ferramentas(...,
  memoria=m)` inclui `consultar_memoria`; sem memória não inclui; observação com o prefixo de
  dados e "HISTÓRICO (não é observação atual)"; memória vazia responde "Nenhum incidente
  confirmado registrado para <servico>."
- [X] T007 [P] [US1] Testes em `tests/test_pipeline_com_memoria.py`: sem memória,
  `confirmar_causa` continua fixa; com memória e `incidente_id`, registra e responde com rota
  `memoria` e o episódio; sem serviço não registra e pede o serviço; troca de causa devolve
  `episodio_anterior` e a resposta avisa a troca; pergunta ("será que foi o deploy?") não
  registra; `incidente_id` passa pela máscara
- [X] T008 [US1] `consultar_memoria` em `agente/ferramentas.py` e regra de memória no prompt do
  agente em `agente/agente_react.py` (inglês, só quando a ferramenta existe, termina com "Always
  answer in Brazilian Portuguese.")
- [X] T009 [US1] `SISTEMA_CAUSA` em `agente/prompts.py` (inglês) e passo 6 com registro da causa
  em `agente/pipeline.py` (`montar_pipeline(..., memoria=None, extrair_causa=None)`; máscara
  preserva `incidente_id`)

## Phase 4: User Story 2 — conversa por sessão com resumo (P2)

**Independent test**: duas sessões isoladas; turno 2 herda o serviço sem histórico repassado;
conversa longa gera resumo e mantém as últimas mensagens.

- [X] T010 [US2] Testes em `tests/test_conversa.py`: `abrir_sessao` gera `uuid4` e metadados;
  turno usa o histórico do checkpointer; sessões não se misturam; `turnos` incrementa e `servico`
  é preenchido pelo NLU; turno bloqueado (moderação, injeção, conteúdo proibido) não é guardado;
  acima do limite resume e mantém as `manter` últimas; falha do resumo mantém tudo; resumo vai ao
  pipeline como mensagem de sistema
- [X] T011 [US2] `SISTEMA_RESUMO` em `agente/prompts.py` (inglês; preserva serviço, sintoma,
  hipóteses levantadas e descartadas, causas confirmadas) e `agente/conversa.py`
  (`Sessao`, `abrir_sessao`, `montar_conversa` com `StateGraph` + `MemorySaver`)
- [X] T012 [US2] `agente/bateria.py`: rodar conversa por sessão (`rodar_conversa_sessao`) e
  colunas "memória registrada" e "memória consultada" em `exibir_bateria`/`exibir_conversa`, com
  testes em `tests/test_bateria_com_memoria.py`

## Phase 5: User Story 3 — explicação e evidência (P3)

- [X] T013 [P] [US3] `dados_dummy/fase3_mensagens.json` (confirmações, perguntas, troca de
  causa, saudação, injeção) e `dados_dummy/fase3_conversas.json` (confirmação + "já aconteceu
  antes?" em outra sessão; decomposição de 4 turnos; conversa longa de 12 turnos; troca de causa);
  `dados_dummy/memoria_longo_prazo.json` com um episódio antigo para o decaimento
- [X] T014 [P] [US3] Diagrama `docs/img/componentes_fase3.png` em `scripts/gerar_diagramas.py`
  (mesma `PALETA`)
- [X] T015 [US3] Seção 3 do `projeto.ipynb`: 3.1 tabela CoALA; 3.2 LangMem × Mem0 × Letta; 3.3
  chatbot com `ConversationBufferMemory` e o mesmo diálogo com `MemorySaver`; 3.4 sessão e resumo;
  3.5 memória episódica (confirmar, trocar causa, consultar); 3.6 interface semântica; 3.7
  decomposição com `AnaliseNLU` por turno; 3.8 bateria e conversas; 3.9 tabela da rubrica.
  Imports no Setup; seção independente; células com modelo com `%%requer_llm`
- [X] T016 [US3] Rodar o notebook inteiro com a chave (`bash -ic`), conferir SC-001 a SC-006,
  0 chaves nos outputs, seções 1 e 2 com os mesmos resultados

## Phase 6: Polish

- [X] T017 README "Como rodar" com a seção 3; `ruff check .` e `ruff format --check .` sem avisos;
  `pytest` verde; artefato `docs/projeto.html` atualizado
- [X] T018 Commit local (sem push)

## Dependencies

T001 → T002 → T003 → T004 → T005 → (T006, T007) → T008 → T009 → T010 → T011 → T012 → T015 →
T016 → T017 → T018. T013 e T014 podem rodar em paralelo a partir de T005.

## Phase 7: Alinhamento com o material de memória (D5 e D6)

- [X] T019 Testes primeiro em `tests/test_memoria.py`: `Episodio` com `id_memoria`, `incidente_id`,
  `thread_id`, `resumo`, `status`, `substitui`, `motivo_registro`, `acessos` (sem
  `historico_causas`); texto indexado = resumo + serviço + causa + evidência; resolvedor falso
  `inserir_novo` cria episódio ativo; `atualizar_existente` arquiva o antigo (continua no store)
  e cria novo ativo com `substitui`; **troca de causa preserva o antigo arquivado e a busca só
  acha o ativo**; **trava**: atualizar episódio de outro `incidente_id` vira inserção com a
  correção no motivo; id inexistente vira inserção; relevância = `0,7*sim + 0,2/(1+0,05*dias) +
  min(0,15; 0,01*acessos)`; consulta incrementa `acessos`; `listar_episodios` mostra ativos e
  arquivados; JSON preserva tudo
- [X] T020 `ResolucaoMemoria`, `ResultadoRegistro`, `montar_resolucao_memoria(llm)` (prompt em
  inglês: incidente diferente = `inserir_novo`) e a nova `MemoriaLongoPrazo` em
  `agente/memoria.py`/`agente/schemas.py`/`agente/prompts.py`; atualizar
  `dados_dummy/memoria_longo_prazo.json`
- [X] T021 Testes primeiro em `tests/test_ferramenta_memoria.py` e
  `tests/test_pipeline_com_memoria.py`: `gravar_episodio` **recusa** quando o turno não é
  `confirmar_causa` (agente de investigação tenta gravar hipótese, nada gravado, observação de
  recusa); grava quando é; serviço e incidente vêm do `ContextoTurno`; confirmação vai ao agente
  de registro e a resposta traz `episodio`, `episodio_anterior` e `resolucao`; sem serviço ou
  incidente: `pedir_servico`/`pedir_incidente`; falha do agente: rota `erro`
- [X] T022 `ContextoTurno`, `gravar_episodio`, agente de registro e prompt de procedimento (inglês)
  em `agente/ferramentas.py`, `agente/agente_react.py`, `agente/pipeline.py`; remover a extração
  `CausaConfirmada` por etapa (vira argumento da ferramenta)
- [X] T023 Testes primeiro em `tests/test_conversa.py`: cada mensagem guardada recebe
  `relevancia` e `motivo`; `baixa` não vai ao histórico do pipeline; erro do avaliador = `alta`;
  janela e resumo continuam; depois `montar_avaliacao_relevancia` e `AvaliacaoRelevancia` em
  `agente/conversa.py`/`agente/schemas.py` (prompt em inglês)
- [X] T024 Ajustar `agente/bateria.py` e `dados_dummy/fase3_*.json` às rotas novas (confirmação
  vira rota `memoria` via agente de registro; mensagem de hipótese com tentativa de gravar)

D7 implementado (itens 1 a 6; item 7 já estava mantido).
