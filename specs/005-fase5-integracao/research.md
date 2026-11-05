# Research: Fase 5

## Mapeamento contra o material da aula (2026-11-05)

| Componente | Peça da aula | Situação |
|---|---|---|
| Auditor | Extração de afirmações com `with_structured_output`; checagem de fatos por função determinística contra uma fonte da verdade com tolerância; verificação de coerência por um LLM juiz que devolve veredito apoia/refuta/neutro, `e_coerente` e falácias. O auditor fica fora do agente e avalia a resposta já pronta | Ensinado (só transcrição e aba; não há notebook) |
| Agente único | `create_agent` + `MemorySaver` / `system_prompt` | Ensinado |
| `create_openai_tools_agent` + `AgentExecutor` | — | Sem equivalente na aula. A rubrica cobra; a constitution V manda mostrar numa célula curta com `langchain-classic` |
| `RunnableWithMessageHistory` | Ensinado em chain da LangChain Expression Language (LCEL), nunca em agente | O projeto já o usa em volta do pipeline (Fase 3) |
| Streamlit | Só citado ("não muda a nota") | Sem equivalente; a constitution X pede |
| LangSmith | Só anunciado (métricas de avaliação e avaliação de trajetória); não há aula 8 no material | Sem equivalente; F5-D2 |
| Trajetória | Callbacks e leitura de `state["messages"]` | Ensinado (base dos avaliadores) |
| Entrega | Relatório organizado, avaliação e trajetória com LangSmith, vídeo (YouTube com link privado é preferível), citar as IAs usadas; prazo citado: dia 13 | Da aula 6 e da aula 7 |

## Decisões

| # | Decisão | Opções | Escolha | Situação |
|---|---|---|---|---|
| F5-D1 | Auditor reprova | A: marca e avisa, sem nova tentativa; B: uma nova tentativa com o motivo; C: bloqueia | A (Jev A 0,91). Fiel à aula: o auditor fica fora do agente | Recomendação aplicada; enviada ao Rafael para validar |
| F5-D2 | API do LangSmith | A: SDK oficial (`Client.create_dataset` + `evaluate` com avaliadores próprios); B: A + LLM juiz (openevals); C: só tracing | A (Jev A 0,85) | Recomendação aplicada; o envio à conta do Rafael espera a confirmação dele |
| — | Agente final | constitution V | `create_agent` como padrão; o clássico numa célula curta | Já decidido |
| — | Streamlit e Docker | constitution X | Duas telas, Dockerfile e compose | Já decidido; corte permitido: só a tela de uso |
| — | Post-mortem | constitution VIII | `.md` por template, só a pedido | Já decidido |
