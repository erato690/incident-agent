# incident-agent

Agente cognitivo que investiga erros de aplicações em produção, conduzindo uma conversa guiada pelas perguntas do engenheiro de plantão — que pode começar só pelo sintoma relatado. Projeto do curso "Agentes Cognitivos com LangChain" (Infnet).

## Status

Fases 1 a 3 concluídas: chain executável com entrada e saída estruturadas (seção 1 do `projeto.ipynb`), agente ReAct com ferramentas só leitura sobre a loja e o GitHub (seção 2) e memória de curto prazo (conversa por sessão com `RunnableWithMessageHistory`, filtro de relevância, `trim_messages` e resumo) e de longo prazo (episódios com causa confirmada num `InMemoryVectorStore`, resolução de memória e busca com decaimento; interface da memória semântica) (seção 3); código em `agente/`, testes em `tests/`. As fases seguintes (banco de incidentes e runbooks, auditor, app Streamlit) ainda não existem neste repositório. Para o histórico de decisões, ver o `HANDOFF.md` no repositório [`agentes-cognitivos`](https://github.com/erato690/agentes-cognitivos) (mesma conta GitHub).

## Como rodar

Requisitos: Python 3.11 ou mais novo.

```bash
python -m venv .venv
source .venv/bin/activate          # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Variáveis (no ambiente ou num arquivo `.env` na raiz; o `.env` não vai para o Git):

```
LLM_PROVEDOR=openai       # openai (padrão) | deepseek
OPENAI_API_KEY=sk-...     # modelo de linguagem da OpenAI, moderação e embeddings da memória
DEEPSEEK_API_KEY=...      # só se LLM_PROVEDOR=deepseek
LOJA_URL=http://localhost:8000   # opcional: incident-shop ao vivo; sem ela, dados_dummy/cenarios/
GITHUB_TOKEN=...          # opcional: sobe o limite da API do GitHub (sem token: 60 por hora)
```

Cada provedor exige a sua chave; não há troca automática. Sem chave, o notebook roda até o fim e pula as células que chamam o modelo de linguagem; sem `OPENAI_API_KEY`, a moderação é pulada com aviso. A busca na memória de longo prazo usa embeddings da OpenAI (`text-embedding-3-small`), então a seção 3 com modelo real exige `OPENAI_API_KEY` mesmo com `LLM_PROVEDOR=deepseek`.

- **Notebook**: abra `projeto.ipynb` no VS Code (extensão Jupyter) ou no Jupyter e rode todas as células. Para executar pela linha de comando: `jupyter nbconvert --to notebook --execute --inplace projeto.ipynb`.
- **Testes**: `pytest -q` (sem chave e sem rede; o modelo e a moderação são substituídos por versões falsas).
- **Diagramas**: `python scripts/gerar_diagramas.py` regenera `docs/img/contexto.png`, `docs/img/componentes.png`, `docs/img/componentes_fase2.png` e `docs/img/componentes_fase3.png`.
- **Memória de longo prazo**: `dados_dummy/memoria_longo_prazo.json` traz um episódio de exemplo; o notebook trabalha numa cópia temporária, então o arquivo não muda.
- **Dados gravados**: `dados_dummy/cenarios/` vem do `scripts/gravar_dados_dummy.py` do `incident-shop` (ou `python scripts/gravar_cenarios.py --url ...`); `python scripts/gravar_github.py` regrava as comparações de versões de reserva.
- **Opcional**: a extensão *Markdown Preview Mermaid Support* (`bierner.markdown-mermaid`) do VS Code renderiza blocos Mermaid em markdown; o notebook não depende dela.

## Repositórios relacionados

- [`incident-shop`](https://github.com/erato690/incident-shop) — interface de programação (API) FastAPI que simula a loja e os cenários de incidente usados pelo agente.
- [`agentes-cognitivos`](https://github.com/erato690/agentes-cognitivos) — material de estudo do curso e histórico de decisões do projeto.

## Arquitetura

- **Barreira de escopo**: o agente só discute o que está no domínio de investigação de incidentes.
- **Memória**: aprende só com fatos confirmados pelo humano; não grava nada sozinho.
- **Auditor de verificação cognitiva**: valida se as conclusões do agente são consistentes com as evidências.
- **Relatório**: gerado em `.md` só quando o engenheiro pede; internamente tudo é JSON (formato de dados em texto).
- **Sem execução de ações**: o agente não executa correções, apenas as sugere.
- **Modelo de linguagem (LLM) de chat**: escolha explícita entre DeepSeek (`ChatDeepSeek`) e OpenAI (`ChatOpenAI("gpt-4o-mini")`) por `LLM_PROVEDOR` (padrão `openai`), sem troca automática. Embeddings: OpenAI `text-embedding-3-small`.
- **Fonte de dados**: lê a variável `LOJA_URL` (API do repositório irmão `incident-shop`, ao vivo); sem ela, lê respostas gravadas em `dados_dummy/<cenario>.json`.
- **Ferramenta real de API externa**: GitHub, função `comparar_versoes` (compara duas tags/commits do repositório `incident-shop` via API REST real do GitHub, funciona sem token).
- **Telas (futuro, Streamlit)**: uso (engenheiro faz perguntas) e análise (trajetória + auditor).
- **Guardrails**: seis camadas (máscara local e moderação, compreensão, ferramentas, dados que voltam, saída, análise); sem tool de escrita; SQL somente leitura.
- **Deploy**: Docker local via `docker compose`; produção no Railway (porta pela variável `PORT`).

## Prazo

Entrega: 09/11/2026.
