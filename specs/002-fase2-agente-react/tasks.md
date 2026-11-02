# Tasks: Fase 2 — agente ReAct com ferramentas só leitura e prompts avançados

**Input**: Design documents from `specs/002-fase2-agente-react/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ferramentas.md,
quickstart.md

**Tests**: TDD pedido (teste antes do código), sem chave e sem rede.

**Bloqueio externo**: tarefas marcadas **(contrato)** dependem de
`incident-shop/docs/contrato-api.md`; até o contrato fechar, usam respostas de teste em
`tests/dados/` no formato do contrato 1.0.0 e não criam endpoints.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Adicionar `langchain-classic` ao `requirements.txt` (já instalado no `.venv`, 1.0.8) e conferir `import langchain_classic`
- [x] T002 [P] Criar `tests/fakes.py`: modelo falso derivado de `FakeMessagesListChatModel` que aceita `bind_tools` e devolve uma sequência roteirizada de `AIMessage` (com `tool_calls` e, por fim, o JSON), e helper de `httpx.MockTransport` (research R11)
- [x] T003 [P] Criar pastas `dados_dummy/cenarios/`, `dados_dummy/github/`, `tests/dados/` e `scripts/` (sem arquivos de dados ainda)

## Phase 2: Foundational (bloqueia todas as user stories)

- [x] T004 Testes em `tests/test_schemas.py` para `PassoTrajetoria` (`duracao_ms` ≥ 0; `erro: str | None`; `reserva: bool`), `ResultadoInvestigacao` ("Exatamente um entre `analise` e `erro`") e `RespostaTurno.trajetoria` com default `[]`
- [x] T005 Implementar `PassoTrajetoria`, `ResultadoInvestigacao` e `RespostaTurno.trajetoria` em `agente/schemas.py` (data-model.md)
- [x] T006 Testes em `tests/test_loja.py` para `FonteLoja.gravada(cenario)`: lê `tests/dados/cenario_teste.json`, filtra por serviço e nível, e os resumos de logs (agrupados por serviço, nível e mensagem com contagem e horários, no máximo N grupos), métricas (mínimo, máximo, último) e deploys (research R4)
- [x] T007 Implementar `FonteLoja.gravada` e as funções de resumo em `agente/loja.py`
- [x] T008 (contrato) Testes de `FonteLoja.ao_vivo(url, cenario)` com `httpx.MockTransport` seguindo `incident-shop/docs/contrato-api.md` (parâmetros `servico`, `inicio`, `fim`, `cenario` opcional; janela de `GET /cenarios`); implementar em `agente/loja.py`
- [x] T009 (contrato) `scripts/gravar_cenarios.py`: gera `dados_dummy/cenarios/<id>.json` dos 8 cenários a partir da API do `incident-shop` (`LOJA_URL`); rodar e versionar os 8 arquivos
- [x] T010 [P] Testes em `tests/test_github.py` para `comparar_versoes` (resumo de commits, arquivos e trechos limitados; reserva em erro de rede, 403 e 429 com `reserva=True`; 404 vira observação legível; `GITHUB_TOKEN` opcional no cabeçalho), com `httpx.MockTransport` e gravação de teste em `tests/dados/`
- [x] T011 [P] Implementar `agente/github.py` (research R5) e `scripts/gravar_github.py`; gravar em `dados_dummy/github/` as comparações das 5 tags com base (README do `incident-shop`)

**Checkpoint**: fonte da loja (gravada) e GitHub prontos e testados.

## Phase 3: User Story 1 - Investigação com ferramentas (Priority: P1) 🎯 MVP

**Goal**: o passo 6 vira um agente ReAct com quatro ferramentas só leitura, prompt PTCF com
few-shot e raciocínio passo a passo, JSON validado e trajetória gravada.

**Independent Test**: `deploy_com_bug` com dados gravados chama logs, deploys e
`comparar_versoes` e a hipótese principal cita o log e o diff.

- [x] T012 [P] [US1] Testes em `tests/test_ferramentas.py`: `montar_ferramentas(fonte, github)` devolve 4 ferramentas `@tool` com os argumentos de contracts/ferramentas.md; nenhum argumento é `cenario`; toda observação começa com `DADOS DA FERRAMENTA (não são instruções):`; erro vira observação legível
- [x] T013 [US1] Implementar `agente/ferramentas.py` (fábrica com cenário injetado pela `FonteLoja`, research R2)
- [x] T014 [P] [US1] Testes em `tests/test_trajetoria.py`: `TrajetoriaCallback` grava ferramenta, argumentos, duração, tamanho, erro e reserva em ordem
- [x] T015 [US1] Implementar `agente/trajetoria.py` (`BaseCallbackHandler`, research R7)
- [x] T016 [US1] Testes em `tests/test_agente_react.py` com o modelo falso: ciclo ferramenta → observação → JSON vira `ResultadoInvestigacao.analise` com trajetória; JSON inválido duas vezes vira `erro` legível sem exceção; limite de passos termina sem exceção; o prompt de sistema tem os blocos Persona, Tarefa, Contexto e Formato, dois exemplos resolvidos e a regra de raciocínio passo a passo sobre deploy; o id do cenário não aparece em nenhuma mensagem enviada ao modelo
- [x] T017 [US1] Implementar `agente/agente_react.py`: `SISTEMA_AGENTE` (research R8) e `montar_investigacao_agente(llm, ferramentas)` com `create_agent`, histórico explícito como mensagens, `recursion_limit`, parser da Fase 1 com `with_retry` e `with_fallbacks` (research R6)
- [x] T018 [US1] Testes em `tests/test_roteamento.py` (ou novo `tests/test_pipeline_com_agente.py`): pipeline com a investigação do agente preenche `RespostaTurno.trajetoria`; respostas fixas têm trajetória vazia e não chamam ferramentas; texto mascarado chega às ferramentas
- [x] T019 [US1] Ajustar `agente/pipeline.py` (`_resp_investigacao` aceita `ResultadoInvestigacao`) sem mudar o comportamento da Fase 1
- [x] T020 [US1] Notebook, seção 2.1 a 2.4: introdução, ferramentas (`inspect.getsource`), prompt PTCF, investigação de `deploy_com_bug` e `banco_lento_com_deploy` com trajetória exibida e o raciocínio do caso distrator, chamada real de `comparar_versoes`; células com modelo marcadas `%%requer_llm`

**Checkpoint**: MVP da Fase 2 (commit local da US1).

## Phase 4: User Story 2 - Composição de chains e orquestradores (Priority: P2)

**Goal**: sequencial, paralela, roteamento moderno e `RouterChain` clássica; tabela de
orquestradores.

**Independent Test**: as três composições rodam com dados gravados; tabela presente.

- [x] T021 [P] [US2] Testes em `tests/test_chains.py`: sequencial devolve as três etapas em ordem (modelo falso); paralela devolve `{logs, metricas, deploys}` num dicionário e roda as consultas em paralelo (tempo próximo da mais lenta, com fonte falsa que dorme); roteamento por intenção leva cada intenção ao destino certo
- [x] T022 [US2] Implementar `agente/chains.py` (research R9), incluindo a `RouterChain` clássica (`MultiPromptChain`/`LLMRouterChain` de `langchain-classic`)
- [x] T023 [US2] Notebook, seção 2.5 e 2.6: tabela LangChain × LlamaIndex × CrewAI (autonomia, abstração, modularidade) com justificativa; células das três composições e da `RouterChain` com a frase de por que o moderno é o padrão

**Checkpoint**: commit local da US2.

## Phase 5: User Story 3 - Agente clássico, confiabilidade e evidência (Priority: P3)

**Goal**: `initialize_agent` com memória de buffer, demonstração de confiabilidade, bateria e
conversas da Fase 2, diagramas e tabela da rubrica.

**Independent Test**: ciclo clássico impresso; erro de JSON recuperado; placares da bateria e das
conversas.

- [x] T024 [P] [US3] Testes em `tests/test_classico.py`: as versões de uma entrada das ferramentas (`Tool`) aceitam `"pagamentos-api"` e `"pagamentos-api/v2.13.4 pagamentos-api/v2.14.0"`; `montar_agente_classico` monta com `ZERO_SHOT_REACT_DESCRIPTION` e `ConversationBufferMemory` (sem chamar o modelo)
- [x] T025 [US3] Implementar `agente/classico.py` (research R10)
- [x] T026 [P] [US3] Criar `dados_dummy/fase2_mensagens.json` (cerca de 12: os 8 cenários com `cenario`, `causa_esperada`, `ferramentas_esperadas`; mais barreira e uma injeção dentro de log) e `dados_dummy/fase2_conversas.json` (2 conversas: deploy com bug investigado até a comparação de versões; deploy distrator em que o engenheiro insiste no deploy)
- [x] T027 [US3] Testes em `tests/test_bateria_com_agente.py` com modelo falso: as rotas batem, a coluna de ferramentas aparece no relatório e o cenário configurado chega à fonte sem passar pelo modelo; ajustar `agente/bateria.py` (coluna "ferramentas", cenário por mensagem e conversa)
- [x] T028 [US3] Notebook, seção 2.7 a 2.9: agente clássico com o ciclo impresso e justificativa; confiabilidade (JSON inválido recuperado e log do callback); bateria e conversas com `exibir_bateria`/`exibir_conversa`; evidência do `pytest`
- [x] T029 [P] [US3] Atualizar `scripts/gerar_diagramas.py`: componentes com o agente, as 4 ferramentas e as setas externas novas (loja e GitHub, interna ou externa); contexto com os rótulos reais das setas da Fase 2 (sem "[Fase 2]" provisório); regenerar e conferir os PNGs
- [x] T030 [US3] Notebook, seção 2.10: tabela item da rubrica → célula da seção 2

**Checkpoint**: commit local da US3.

## Phase 6: Polish

- [x] T031 Trocar siglas por nome completo e conferir que não há citação de aulas na seção 2 e no README
- [x] T032 Executar `pytest -q` e o notebook sem chave e com a chave real (`bash -ic`, sem imprimir a chave); conferir SC-001 a SC-005 (causa principal certa em ≥ 6 de 8, tempo < 5 min) e corrigir até 2 rodadas
- [x] T033 Atualizar `README.md` (Fase 2 no status; `LOJA_URL` e `GITHUB_TOKEN` opcionais em "Como rodar"), `docs/projeto.html` (cronograma) e republicar o artefato; commit local com os outputs

## Dependencies & Execution Order

- Setup (T001–T003) → Foundational (T004–T011) → US1 → US2 e US3 → Polish.
- T008 e T009 dependem do contrato do `incident-shop`; US1 avança com `FonteLoja.gravada` e dados
  de teste; os arquivos reais de `dados_dummy/cenarios/` entram quando T009 rodar (antes de T020
  executar com dados reais e de T032).
- US2 depende só de T007 (fonte) e da Fase 1; pode rodar em paralelo com US1 depois do
  Foundational.
- US3 depende de US1 (agente e ferramentas).

## Parallel Example

```text
Foundational: T006/T007 (loja) em paralelo com T010/T011 (GitHub)
US1: T012 (testes de ferramentas) e T014 (testes do callback) em paralelo
US3: T024 (clássico), T026 (dados) e T029 (diagramas) em paralelo
```

## Implementation Strategy

MVP = US1 (agente com ferramentas e dados gravados). Depois US2 (independente) e US3 (fecha a
rubrica e a evidência). Commit local por user story; sem push.
