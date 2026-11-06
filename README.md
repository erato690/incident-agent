# incident-agent

Agente cognitivo que investiga erros de aplicações em produção, conduzindo uma conversa guiada pelas perguntas do engenheiro de plantão — que pode começar só pelo sintoma relatado. Projeto do curso "Agentes Cognitivos com LangChain" (Infnet).

## Status

Fases 1 a 5 concluídas: chain executável com entrada e saída estruturadas (seção 1 do `projeto.ipynb`), agente ReAct com ferramentas só leitura sobre a loja e o GitHub (seção 2) e memória de curto prazo (conversa por sessão com `RunnableWithMessageHistory`, filtro de relevância, `trim_messages` e resumo) e de longo prazo (episódios com causa confirmada num `InMemoryVectorStore`, resolução de memória e busca com decaimento; interface da memória semântica) (seção 3), e ferramentas externas (seção 4): consulta SQL só leitura sobre `dados/incidentes.db`, recuperação de documentos (RAG) sobre o índice FAISS `dados/indice_faiss/` com runbooks em `dados/documentos/`, estatísticas do banco do incident-shop (contrato 1.1.0), memória semântica com fonte, data e validade, e ações sugeridas (nunca executadas); código em `agente/`, testes em `tests/`. Na seção 5, o agente integrado (`agente/integrado.py`) junta tudo atrás da barreira, com auditor de verificação (`agente/auditor.py`), post-mortem `.md` a pedido (`agente/postmortem.py`) e avaliação (`agente/avaliacao.py`, `scripts/avaliar_langsmith.py`). A interface web própria (FastAPI com front HTML, CSS e JavaScript em `app/`) roda com `uvicorn app.main:app --host 127.0.0.1 --port 8501` ou `docker compose up`, em http://127.0.0.1:8501. A seção 0 do notebook mostra o agente final e o índice da rubrica. O relatório técnico está em `docs/relatorio.md`, e o PDF sai de `scripts/gerar_relatorio_pdf.py`. Para o histórico de decisões, ver o `HANDOFF.md` no repositório [`agentes-cognitivos`](https://github.com/erato690/agentes-cognitivos) (mesma conta GitHub).

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

Cada provedor exige a sua chave; não há troca automática. Sem chave, o notebook roda até o fim e pula as células que chamam o modelo de linguagem; sem `OPENAI_API_KEY`, a moderação é pulada com aviso. A busca na memória de longo prazo usa embeddings da OpenAI (`text-embedding-3-small`), então as seções 3 e 4 com modelo real exigem `OPENAI_API_KEY` mesmo com `LLM_PROVEDOR=deepseek`. O índice FAISS já vem no repositório; para reconstruí-lo, `python scripts/construir_indice.py` (com a chave). A base SQLite sai de `python scripts/construir_sqlite.py` (sem chave).

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
- **Auditor de verificação cognitiva**: valida se as conclusões do agente são consistentes com as evidências, com as técnicas vistas na disciplina: extração das afirmações com Pydantic (`with_structured_output`), checagem de fatos determinística (`checar_fatos`, métrica `fato_deterministico`), inferência lógica (NLI) com veredito explícito `apoia`, `refuta` ou `neutra` e falácias do domínio (métrica `veredito_nli`), e avaliação da trajetória (`trajetoria_ferramentas`). O veredito do juiz é rebaixado por código quando contradiz a checagem de fatos.
- **Relatório**: gerado em `.md` só quando o engenheiro pede; internamente tudo é JSON (formato de dados em texto).
- **Sem execução de ações**: o agente não executa correções, apenas as sugere.
- **Modelo de linguagem (LLM) de chat**: escolha explícita entre DeepSeek (`ChatDeepSeek`) e OpenAI (`ChatOpenAI("gpt-4o-mini")`) por `LLM_PROVEDOR` (padrão `openai`), sem troca automática. Embeddings: OpenAI `text-embedding-3-small`.
- **Fonte de dados**: lê a variável `LOJA_URL` (API do repositório irmão `incident-shop`, ao vivo); sem ela, lê respostas gravadas em `dados_dummy/<cenario>.json`.
- **Ferramenta real de API externa**: GitHub, função `comparar_versoes` (compara duas tags/commits do repositório `incident-shop` via API REST real do GitHub, funciona sem token).
- **Telas (interface web própria)**: uso (conversa por incidente, com barra lateral de sessões) e análise (trajetória + auditor).
- **Guardrails**: seis camadas (máscara local e moderação, compreensão, ferramentas, dados que voltam, saída, análise); sem tool de escrita; SQL somente leitura.
- **Deploy**: Docker local via `docker compose`; produção no Railway (porta pela variável `PORT`).

## Prazo

Entrega: 09/11/2026.

## Laboratório com Docker Compose

O laboratório `incident-lab` (em `../laboratorios/incident-lab/`) sobe a loja `incident-shop`
(contrato 1.1.0) e este agente já conectados, com um comando:

```bash
cd ../laboratorios/incident-lab
docker compose up --build    # chat em http://127.0.0.1:8501, loja em http://127.0.0.1:8000
docker compose down
```

- **Variáveis:** `CENARIO` (cenário das conversas novas, padrão `pool_esgotado`), `AGENTE_PORTA`,
  `SHOP_PORTA`, `SHOP_CONTEXTO` e `AGENTE_CONTEXTO`; portas só em 127.0.0.1.
- **Chave:** vem do shell ou do `.env` deste projeto, nunca da imagem.
- **Ao vivo × gravado:** no laboratório, `LOJA_URL=http://shop:8000` faz as ferramentas chamarem a
  loja (veja as requisições com `docker compose logs -f shop`). Fora dele, sem `LOJA_URL`, o
  agente usa `dados_dummy/`, e as baterias, o notebook e a avaliação seguem determinísticos.
- O `docker-compose.yml` deste repositório continua subindo só o app. O deploy no Railway não faz
  parte do laboratório.

