# Implementation Plan: Fase 4 — ferramentas externas, consulta SQL e RAG

**Branch**: `004-fase4-ferramentas-rag` (trabalho em `main`, commits locais) | **Date**: 2026-11-05 |
**Spec**: [spec.md](spec.md)

## Summary

Seção 4 do `projeto.ipynb`. O Investigador ganha quatro ferramentas, todas só leitura fora da
memória do próprio agente:

- `consultar_estatisticas_banco` é hardcoded e chama a API interna do incident-shop 1.1.0.
- `buscar_documentacao` é RAG (recuperação de documentos) sobre um índice FAISS existente, de
  runbooks e documentação.
- `consultar_wiki` é a memória semântica. Busca primeiro na wiki, depois na documentação; se não
  achar, devolve a pergunta para o usuário.
- `sugerir_acao` é semântica: um LLM dentro da ferramenta, mais o runbook.

A confirmação de um fato pelo engenheiro (intenção `confirmar_fato`) vai ao Registrador, com a
ferramenta `gravar_fato` protegida por trava. Dois agentes isolados mostram os itens da rubrica:

- o agente de consulta SQL (`consultar_sql` sobre SQLite, lista negra da aula 6);
- o agente de recuperação, com a falha de recuperação diagnosticada (pergunta crua × reescrita,
  com scores).

Decisões em [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.11+ (local 3.14)

**Primary Dependencies**: as das Fases 1 a 3, mais `faiss-cpu`, `langchain-community`
(`FAISS`) e `langchain-text-splitters` (`RecursiveCharacterTextSplitter`). `sqlite3` vem da
biblioteca padrão.

**Storage**:

| Dado | Onde fica | Como é gerado ou gravado |
|---|---|---|
| Base SQLite | `dados/incidentes.db` | `scripts/construir_sqlite.py`, determinístico, sem chave |
| Índice FAISS | `dados/indice_faiss/` | `scripts/construir_indice.py`, com a chave (embeddings da OpenAI) |
| Corpus | `dados/documentos/*.md` | escrito para o projeto |
| Estatísticas do banco | `dados_dummy/cenarios/*.json`, chave `estatisticas_banco` | gravadas por cenário |

**Testing**: `pytest` com modelo falso, `DeterministicFakeEmbedding`, índice FAISS temporário e
SQLite temporária. Sem chave e sem rede.

**Performance Goals**: seção 4 com a chave em até 300 s.

**Constraints**:

- Nenhuma ferramenta escreve fora da memória do agente.
- `gravar_fato` só grava na intenção `confirmar_fato`.
- A base SQLite nunca muda por consulta.
- O texto que vem da documentação é dado, nunca instrução (camada 4), e passa pela máscara.
- As seções 1 a 3 e as baterias delas ficam inalteradas, porque as ferramentas novas são
  opcionais e injetadas.

**Scale/Scope**: 5 user stories, 3 módulos novos (`sql.py`, `recuperacao.py`, `acoes.py`), ~10
documentos, cerca de 12 mensagens de bateria.

## Constitution Check

| Princípio | Como o plano cumpre | Status |
|---|---|---|
| I. Só leitura | SQL com lista negra + `SELECT`; estatísticas por GET; sugestão sem execução | OK |
| II. Evidência | Estatística, fato (fonte e data) e runbook citados na evidência | OK |
| III. Barreira | Barreira intacta; `confirmar_fato` passa pela mesma barreira | OK |
| IV. Memória | Fato só com fonte e data; fato do usuário só depois de confirmado | OK |
| V. Padrões da aula | `@tool` + Pydantic, `sqlite3`, `FAISS.load_local`, `similarity_search_with_score`, `create_retriever_tool` (comparação), `create_agent` | OK |
| VI. Modelos | Mesmo `llm`; embeddings da OpenAI só com chave | OK |
| VII. Offline | Sem chave: embedding falso nos testes; células com modelo puladas | OK |
| VIII. JSON | `AcaoSugerida`, `EstatisticaTabela` e `FatoSemantico` em Pydantic | OK |
| IX. Escopo | Itens da rubrica + escopo combinado (D1) | OK |
| X. Entrega | Seção 4 no notebook único | OK |

## Project Structure

```text
agente/
├── sql.py            # BancoSQL (sqlite3), validar_consulta (lista negra), ferramenta consultar_sql
├── recuperacao.py    # carregar_indice (FAISS.load_local), buscar_com_score, ferramenta buscar_documentacao
├── acoes.py          # AcaoSugerida, ferramenta semântica sugerir_acao (LLM + runbook)
├── loja.py           # + FonteLoja.estatisticas_banco, resumir_estatisticas (contrato 1.1.0)
├── ferramentas.py    # + consultar_estatisticas_banco, consultar_wiki, gravar_fato
├── schemas.py        # + AcaoSugerida, acoes_sugeridas, confirmar_fato, ContextoTurno.acoes/fato
├── agente_react.py   # regras novas no prompt (banco, dependência externa, wiki, ação)
├── prompts.py        # NLU com confirmar_fato; SISTEMA_ACAO
├── pipeline.py       # confirmar_fato -> Registrador com gravar_fato; acoes copiadas por código
└── bateria.py        # causa_certa (palavras_causa)
dados/
├── documentos/*.md   # runbooks e documentação (PagaFácil)
├── indice_faiss/     # index.faiss + index.pkl
└── incidentes.db
scripts/construir_sqlite.py, scripts/construir_indice.py
dados_dummy/fase4_mensagens.json, fase4_conversas.json
tests/test_sql.py, test_recuperacao.py, test_acoes.py, test_estatisticas_banco.py, test_wiki.py,
      test_pipeline_fase4.py
```

## Fluxos

1. **Investigação, `banco_lento`:**
   1. `buscar_logs` mostra timeout e lock.
   2. A regra do banco leva a `consultar_estatisticas_banco(pedidos-api)`, que mostra
      `manutencao_em_andamento: REINDEX TABLE estoque`.
   3. Hipótese principal: reindexação. O deploy fica descartado.
   4. `sugerir_acao` traz o runbook de reindexação.
2. **Investigação, `rate_limit`:**
   1. `buscar_logs` mostra o 429 do PagaFácil.
   2. `consultar_wiki("PagaFácil", "limite de requisições")` não acha fato na wiki e busca na
      documentação.
   3. Grava o fato (fonte "documentacao", validade de 90 dias): limite de 100 por minuto.
   4. `buscar_metricas` mostra requisições de 213 a 237 por minuto, acima do limite.
   5. Hipótese principal: limite estourado.
3. **Fato ausente:** `consultar_wiki` devolve "NÃO ENCONTRADO: pergunte ao usuário <pergunta>".
   A análise traz a pergunta em `dado_que_falta` e em `proximos_passos`. No turno seguinte, o
   engenheiro escreve "Confirmado: o limite do X é Y". O NLU classifica `confirmar_fato`, o
   Registrador chama `gravar_fato` e o fato é gravado com fonte "usuario".
4. **Ações sugeridas:** `sugerir_acao(diagnostico, servico)` busca o runbook e pede ao LLM as
   ações com `with_structured_output`. As ações ficam no contexto do turno e o pipeline as copia
   para `acoes_sugeridas`, todas com `status="sugerida (não executada)"`.

Re-check pós-design: sem violações.
