# Implementation Plan: Fase 1 — chain executável com entrada e saída estruturadas

**Branch**: `001-fase1-chain-mvp` (trabalho em `main`, commits locais) | **Date**: 2026-11-01 |
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-fase1-chain-mvp/spec.md`

## Summary

Seção 1 do `projeto.ipynb`: pipeline LCEL que mascara segredos, modera (OpenAI, pula com aviso),
classifica intenção com o NLU estruturado, roteia com `RunnableBranch` para resposta fixa ou
investigação, e na investigação pré-processa o erro (função no pipe), chama o LLM e valida um
JSON de análise do incidente. A seção também traz as evidências da rubrica: templates,
`invoke`/`batch`/`stream`, demonstração de `@chain`, justificativa LCEL e resumos do desenho.
Funções determinísticas e schemas ficam em `agente/` com testes; o que é avaliado fica visível
nas células. Detalhes em [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.11+ (local 3.14; Colab 3.12)

**Primary Dependencies**: `langchain`, `langchain-core`, `langchain-deepseek`,
`langchain-openai`, `openai`, `pydantic>=2`, `python-dotenv`, `jupyter`

**Storage**: N/A (mensagens de teste em `dados_dummy/fase1_mensagens.json`)

**Testing**: `pytest` para máscara, pré-processamento, schemas e roteamento com NLU falso;
bateria de mensagens no notebook para o comportamento com LLM

**Target Platform**: Jupyter local e Google Colab

**Project Type**: notebook + pacote Python de apoio (`agente/`)

**Performance Goals**: seção 1 completa em menos de 3 minutos (SC-001)

**Constraints**: roda sem `LOJA_URL` e sem `OPENAI_API_KEY`; nenhum segredo sai da máquina;
nenhuma tool de escrita

**Scale/Scope**: ~16 mensagens de teste; 1 seção do notebook; ~6 módulos em `agente/`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Como o plano cumpre | Status |
|---|---|---|
| I. Só leitura | Fase 1 não tem ferramentas; respostas só sugerem | OK |
| II. Evidência | Hipótese exige `evidencia` não vazia; `evidencia_insuficiente` no schema; auditor fora (Fase 5) | OK |
| III. Barreira de escopo | Moderação → NLU → `RunnableBranch` com respostas fixas | OK |
| IV. Memória | Fase 1 só recebe histórico explícito; nenhuma escrita em memória | OK (N/A) |
| V. Padrões das aulas | LCEL, `with_structured_output`, função no pipe + demo `@chain`; nenhuma API clássica nesta fase | OK |
| VI. Modelos | `escolher_llm()` no setup, `FORCAR_PLANO_B`, imprime o modelo | OK |
| VII. Offline | Moderação pula com aviso; dados de teste locais; sem código da loja | OK |
| VIII. JSON | Trocas 1, 2 e 3 em Pydantic; relatório fora desta fase | OK |
| IX. Escopo mínimo | 3 user stories, 1 seção, tabela de rubrica na spec | OK |
| X. Entrega | Seção 1 dentro do notebook único; `.env` fora do git | OK |
| Guardrails | Camadas 1, 2 e 5 (máscara) implementadas aqui | OK |

Re-check pós-design: sem violações. Complexity Tracking vazio.

## Project Structure

### Documentation (this feature)

```text
specs/001-fase1-chain-mvp/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/pipeline.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
projeto.ipynb                 # notebook único; esta feature cria o setup e a seção 1
requirements.txt
.env.example
agente/
├── __init__.py
├── config.py                 # escolher_llm(), carga do .env
├── schemas.py                # modelos Pydantic do data-model
├── mascara.py                # mascarar()
├── preprocessamento.py       # preprocessar(), impressão digital
├── moderacao.py              # moderar()
├── prompts.py                # PromptTemplate (respostas fixas) e ChatPromptTemplate (NLU, investigação)
└── pipeline.py               # montar_pipeline(llm, moderar): composição LCEL com RunnableBranch
dados_dummy/
└── fase1_mensagens.json      # bateria da seção 1
tests/
├── test_mascara.py
├── test_preprocessamento.py
├── test_schemas.py
└── test_roteamento.py        # pipeline com NLU e LLM falsos
```

**Structure Decision**: notebook único na raiz (princípio X) e pacote `agente/` com todo o
código reaproveitado pelas fases seguintes, pelo `app/` e pelos testes, incluindo templates e
a composição LCEL (`montar_pipeline`). Para a rubrica, a seção 1 exibe o código de
`prompts.py` e `pipeline.py` com `inspect.getsource` antes de executá-lo, e escreve direto em
células só o que é demonstração: chamadas `invoke`/`batch`/`stream`, demo `@chain`, bateria e
textos de justificativa (R8). Assim não há código duplicado entre notebook, testes e `app/`.

## Complexity Tracking

Sem violações da constitution.
