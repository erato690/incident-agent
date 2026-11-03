# Implementation Plan: Fase 3 — memória de curto e longo prazo

**Branch**: `003-fase3-memoria` (trabalho em `main`, commits locais) | **Date**: 2026-11-02 |
**Spec**: [spec.md](spec.md)

## Summary

Seção 3 do `projeto.ipynb`. O pipeline das Fases 1 e 2 não muda por dentro: um grafo fino do
LangGraph o envolve, guarda a conversa por sessão (`MemorySaver`, `thread_id = uuid4`) e resume as
mensagens antigas quando a conversa cresce. A memória de longo prazo (`MemoriaLongoPrazo`) fica num
`InMemoryStore` com embeddings, salvo em JSON, com dois espaços separados: episódica (incidentes
com causa confirmada, implementada) e semântica (wiki de fatos com fonte, data e validade, só
interface). `confirmar_causa` registra ou atualiza o episódio; a ferramenta `consultar_memoria`
deixa o agente buscar incidentes anteriores com filtro por serviço e decaimento temporal. A seção
traz a tabela da CoALA, a comparação LangMem × Mem0 × Letta, o chatbot clássico com
`ConversationBufferMemory` ao lado do grafo com `MemorySaver`, a conversa de decomposição, bateria
e conversas com a chave e o diagrama atualizado. Decisões em [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.11+ (local 3.14; Colab 3.12)

**Primary Dependencies**: as das Fases 1 e 2; `langgraph` (já instalado: `StateGraph`,
`MemorySaver`, `InMemoryStore`), `langchain-openai` (`OpenAIEmbeddings`), `langchain-classic`
(`ConversationBufferMemory`). Nenhuma dependência nova.

**Storage**: memória de curto prazo em processo (`MemorySaver`); memória de longo prazo em
`InMemoryStore` com cópia em JSON (`dados_dummy/memoria_longo_prazo.json` para a demonstração;
arquivo temporário nos testes)

**Testing**: `pytest` com modelo falso, `DeterministicFakeEmbedding` e relógio injetado; sem chave
e sem rede

**Target Platform**: Jupyter local e Google Colab

**Project Type**: notebook + pacote Python de apoio (`agente/`)

**Performance Goals**: seção 3 completa com a chave em menos de 5 minutos (SC-006)

**Constraints**: só `confirmar_causa` escreve na memória episódica; nada escreve na semântica
fora de testes e demonstração; seções 1 e 2 e suas baterias inalteradas (memória opcional,
injetada); prompts novos em inglês terminando em "Always answer in Brazilian Portuguese."

**Scale/Scope**: 3 user stories, 2 módulos novos (`memoria.py`, `conversa.py`), ~5 conversas e
~8 mensagens de bateria

## Constitution Check

| Princípio | Como o plano cumpre | Status |
|---|---|---|
| I. Só leitura | `consultar_memoria` só lê; a única escrita é na memória do agente | OK |
| II. Evidência | Episódio citado como histórico, nunca como observação atual | OK |
| III. Barreira | Barreira intacta; mensagens bloqueadas não entram na conversa guardada | OK |
| IV. Memória | `MemorySaver` por incidente com resumo (sem corte por tokens); longo prazo só com confirmação explícita | OK |
| V. Padrões | `MemorySaver`, `StateGraph`, `with_structured_output`, `@tool`; clássico só em célula curta | OK |
| VI. Modelos | Mesmo `llm`; embeddings da OpenAI só com chave (o DeepSeek não tem embeddings) | OK |
| VII. Offline | Sem chave: embedding falso nos testes e células com modelo puladas | OK |
| VIII. JSON | `Episodio`, `FatoSemantico`, `Sessao`, `CausaConfirmada` em Pydantic | OK |
| IX. Escopo | 3 user stories; wiki completa e estatísticas do banco fora (D1) | OK |
| X. Entrega | Seção 3 no notebook único | OK |
| Guardrails | Camada 1 (texto guardado mascarado), camada 4 (memória recuperada é dado) | OK |

Re-check pós-design: sem violações.

## Project Structure

```text
specs/003-fase3-memoria/
├── plan.md, research.md, data-model.md, quickstart.md
├── contracts/memoria.md
└── tasks.md

agente/
├── memoria.py        # Episodio, FatoSemantico, MemoriaLongoPrazo (InMemoryStore + JSON), embeddings_padrao
├── conversa.py       # Sessao, abrir_sessao, montar_conversa (StateGraph + MemorySaver + resumo)
├── schemas.py        # + CausaConfirmada; RespostaTurno com rota "memoria", episodio, episodio_anterior
├── prompts.py        # + SISTEMA_CAUSA, SISTEMA_RESUMO (inglês)
├── pipeline.py       # montar_pipeline(..., memoria=None): passo 6 registra a causa quando há memória
├── ferramentas.py    # + consultar_memoria quando há memória
├── agente_react.py   # regra de memória no prompt quando a ferramenta existe
└── bateria.py        # colunas de memória (registro, consulta); conversa por sessão
dados_dummy/
├── fase3_mensagens.json
├── fase3_conversas.json
└── memoria_longo_prazo.json   # episódio antigo de exemplo (decaimento)
tests/
├── test_memoria.py
├── test_conversa.py
├── test_pipeline_com_memoria.py
└── test_ferramenta_memoria.py
scripts/gerar_diagramas.py      # + componentes_fase3.png
```

**Structure Decision**: mesmo padrão das fases anteriores; a memória entra por injeção
(`memoria=`) para não mudar as seções 1 e 2.

## Complexity Tracking

Sem violações da constitution.
