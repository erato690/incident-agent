# incident-agent

Agente cognitivo que investiga erros de aplicações em produção, conduzindo uma conversa guiada pelas perguntas do engenheiro de plantão — que pode começar só pelo sintoma relatado. Projeto do curso "Agentes Cognitivos com LangChain" (Infnet).

## Status

Em planejamento. A maior parte do código (notebook, agente, app Streamlit) ainda não existe neste repositório. Para o estado detalhado e os próximos passos, ver o `HANDOFF.md` no repositório [`agentes-cognitivos`](https://github.com/erato690/agentes-cognitivos) (mesma conta GitHub).

## Repositórios relacionados

- [`incident-shop`](https://github.com/erato690/incident-shop) — API FastAPI que simula a loja e os cenários de incidente usados pelo agente.
- [`agentes-cognitivos`](https://github.com/erato690/agentes-cognitivos) — material de estudo do curso e histórico de decisões do projeto.

## Arquitetura

- **Barreira de escopo**: o agente só discute o que está no domínio de investigação de incidentes.
- **Memória**: aprende só com fatos confirmados pelo humano; não grava nada sozinho.
- **Auditor de verificação cognitiva**: valida se as conclusões do agente são consistentes com as evidências.
- **Relatório**: gerado em `.md` só quando o engenheiro pede; internamente tudo é JSON.
- **Sem execução de ações**: o agente não executa correções, apenas as sugere.
- **LLM de chat**: DeepSeek (`ChatDeepSeek`), com plano B automático para `ChatOpenAI("gpt-4o-mini")` quando não há `DEEPSEEK_API_KEY`. Embeddings: OpenAI `text-embedding-3-small`.
- **Fonte de dados**: lê a variável `LOJA_URL` (API do repositório irmão `incident-shop`, ao vivo); sem ela, lê respostas gravadas em `dados_dummy/<cenario>.json`.
- **Ferramenta real de API externa**: GitHub, função `comparar_versoes` (compara duas tags/commits do repositório `incident-shop` via API REST real do GitHub, funciona sem token).
- **Telas (futuro, Streamlit)**: uso (engenheiro faz perguntas) e análise (trajetória + auditor).
- **Guardrails**: cinco camadas; sem tool de escrita; SQL somente leitura.
- **Deploy**: Docker local via `docker compose`; produção no Railway (porta pela variável `PORT`).

## Prazo

Entrega: 09/11/2026.
