# Implementation Plan: Fase 2 — agente ReAct com ferramentas só leitura e prompts avançados

**Branch**: `002-fase2-agente-react` (trabalho em `main`, commits locais) | **Date**: 2026-11-01 |
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-fase2-agente-react/spec.md`

## Summary

Seção 2 do `projeto.ipynb`. A entrada da Fase 1 (máscara, moderação, compreensão, roteador) não
muda; o passo 6 (investigação) passa a ser um agente ReAct (`create_agent`) com quatro
ferramentas só leitura: `buscar_logs`, `buscar_metricas`, `listar_deploys` (API do
`incident-shop` ao vivo ou respostas gravadas) e `comparar_versoes` (API REST real do GitHub,
reserva gravada). O agente segue um prompt Persona-Tarefa-Contexto-Formato com dois incidentes
resolvidos como exemplo e raciocínio passo a passo, termina com o JSON da análise, e o parser da
Fase 1 (com nova tentativa e reserva) valida. Um callback grava a trajetória, que vai para a
`RespostaTurno`. A seção também traz as composições da rubrica (sequencial, paralela,
roteamento com `RouterChain` clássica), o agente clássico `initialize_agent`, a tabela de
orquestradores, bateria e conversas com cenário configurado, e diagramas atualizados. Detalhes
em [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.11+ (local 3.14; Colab 3.12)

**Primary Dependencies**: as da Fase 1 + `langchain` 1.x (`create_agent`, `@tool`),
`langchain-classic` (demonstrações), `httpx` (loja e GitHub; já instalado como dependência)

**Storage**: arquivos JSON em `dados_dummy/` (respostas gravadas da loja e do GitHub, mensagens e
conversas de teste)

**Testing**: `pytest` com modelo de linguagem falso que emite chamadas de ferramenta e transporte
HTTP falso (`httpx.MockTransport`); sem chave e sem rede

**Target Platform**: Jupyter local e Google Colab

**Project Type**: notebook + pacote Python de apoio (`agente/`)

**Performance Goals**: seção 2 completa com a chave real em menos de 5 minutos (SC-005)

**Constraints**: roda sem `LOJA_URL`, sem rede e sem chave (pula células com modelo); nenhuma
ferramenta de escrita; o id do cenário nunca chega ao modelo; formatos da loja conforme o
contrato 1.0.0 do `incident-shop` (`docs/contrato-api.md`)

**Scale/Scope**: 8 cenários, 4 ferramentas, ~12 mensagens na bateria, 2 conversas; ~5 módulos
novos em `agente/`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Como o plano cumpre | Status |
|---|---|---|
| I. Só leitura | Quatro ferramentas só de leitura (GET); nenhuma escreve ou executa | OK |
| II. Evidência | Evidência de hipótese sustentada cita observação de ferramenta; CoT verifica deploy antes do sintoma e relação com o erro; `dado_que_falta` sem sustentação | OK |
| III. Barreira | Entrada da Fase 1 intacta; respostas fixas não chamam ferramentas | OK |
| IV. Memória | Histórico explícito por turno (decisão do Rafael); nenhuma escrita em memória | OK |
| V. Padrões | `create_agent` + `@tool` como padrão; `initialize_agent`, `ConversationBufferMemory` e `RouterChain` só em células curtas via `langchain-classic`, com justificativa; PTCF e CoT presentes | OK |
| VI. Modelos | Mesmo `llm` do setup; nada novo | OK |
| VII. Offline | Loja: `LOJA_URL` ou `dados_dummy/`; GitHub real com reserva gravada; código da loja fora do notebook | OK |
| VIII. JSON | `AnaliseIncidente` reaproveitado; trajetória e respostas de ferramenta em Pydantic | OK |
| IX. Escopo | 3 user stories, 1 seção, tabela de rubrica na spec | OK |
| X. Entrega | Seção 2 no notebook único | OK |
| Guardrails | Camada 3 (só leitura) e camada 4 (saída de ferramenta é dado, no prompt e no resumo) | OK |

Re-check pós-design: sem violações. Complexity Tracking vazio.

## Project Structure

### Documentation (this feature)

```text
specs/002-fase2-agente-react/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/ferramentas.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
projeto.ipynb                 # esta feature cria a seção 2
requirements.txt              # + langchain-classic
agente/
├── loja.py                   # FonteLoja: ao vivo (LOJA_URL, contrato do incident-shop) ou gravada; resumos
├── github.py                 # comparar_versoes: API REST do GitHub + reserva gravada; resumo do diff
├── ferramentas.py            # montar_ferramentas(fonte, github): @tool só leitura; cenário injetado
├── trajetoria.py             # TrajetoriaCallback (BaseCallbackHandler)
├── agente_react.py           # prompt PTCF + few-shot + CoT; montar_investigacao_agente(llm, ferramentas)
├── chains.py                 # sequencial, paralela, roteamento (moderno) e RouterChain (clássica)
├── classico.py               # initialize_agent ZERO_SHOT_REACT_DESCRIPTION + ConversationBufferMemory
├── schemas.py                # + PassoTrajetoria, RespostaTurno.trajetoria
├── pipeline.py               # montar_etapas/montar_pipeline aceitam a investigação do agente
└── bateria.py                # + coluna de ferramentas; cenário por mensagem/conversa
scripts/
├── gravar_cenarios.py        # gera dados_dummy/cenarios/<id>.json a partir da API do incident-shop
└── gravar_github.py          # gera dados_dummy/github/<base>...<nova>.json (reserva)
dados_dummy/
├── cenarios/<cenario>.json   # 8 arquivos
├── github/*.json             # comparações gravadas
├── fase2_mensagens.json
└── fase2_conversas.json
tests/
├── fakes.py                  # modelo falso com chamadas de ferramenta; transporte HTTP falso
├── test_loja.py
├── test_github.py
├── test_ferramentas.py
├── test_agente_react.py
├── test_chains.py
└── test_bateria_com_agente.py
```

**Structure Decision**: mesmo padrão da Fase 1: código reaproveitável em `agente/` com testes; o
notebook mostra o código com `inspect.getsource` e executa as demonstrações. O pipeline da Fase 2
é o da Fase 1 com a investigação injetada (`montar_pipeline(llm, moderar,
investigacao=montar_investigacao_agente(...))`), sem duplicar a entrada.

## Complexity Tracking

Sem violações da constitution.
