# incident-agent

Agente cognitivo que investiga erros de aplicações em produção, conduzindo uma conversa guiada pelas perguntas do engenheiro de plantão — que pode começar só pelo sintoma relatado. Projeto do curso "Agentes Cognitivos com LangChain" (Infnet).

## Por onde começar (avaliação)

| O que | Onde |
|---|---|
| **Notebook completo** (da chain inicial ao agente integrador) | [`projeto.ipynb`](projeto.ipynb), na raiz deste repositório. O GitHub o mostra no navegador, já com as saídas de cada célula. |
| Código do agente | `agente/` (pipeline, ferramentas, memória, auditor, avaliação) e `app/` (interface web) |
| Dados e alternativas sem credencial | `dados_dummy/` (cenários gravados da loja, memória de exemplo); `dados/` (banco SQLite e índice de documentos) |
| Testes | `pytest -q`, sem chave e sem rede |
| Relatório técnico (PDF) e vídeo | entregues pelo Moodle |

**Ver o notebook sem rodar nada:** abra [`projeto.ipynb`](projeto.ipynb) aqui no GitHub. Ele está
dividido por capacidade: seção 0 (visão geral e índice da rubrica), 1 (chain com saída estruturada),
2 (agente com ferramentas), 3 (memória), 4 (SQL e RAG) e 5 (agente integrado, auditor e avaliação).

**Rodar o notebook:** clone o repositório (o notebook importa o pacote `agente/`, então precisa do
repositório inteiro), crie o ambiente e instale as dependências (seção "Como rodar"), e abra
`projeto.ipynb` no VS Code ou no Jupyter. Sem chave, ele roda até o fim com os dados gravados em
`dados_dummy/` e pula só as células que chamam o modelo. Para ver o agente conversando, use a seção
abaixo.

## Status

Fases 1 a 5 concluídas: chain executável com entrada e saída estruturadas (seção 1 do `projeto.ipynb`), agente ReAct (raciocinar e agir) com ferramentas só leitura sobre a loja e o GitHub (seção 2) e memória de curto prazo (conversa por sessão com `RunnableWithMessageHistory`, filtro de relevância, `trim_messages` e resumo) e de longo prazo (episódios com causa confirmada num `InMemoryVectorStore`, resolução de memória e busca com decaimento; interface da memória semântica) (seção 3), e ferramentas externas (seção 4): consulta SQL só leitura sobre `dados/incidentes.db`, recuperação de documentos (RAG, geração aumentada por recuperação) sobre o índice FAISS `dados/indice_faiss/` com runbooks em `dados/documentos/`, estatísticas do banco do incident-shop (contrato 1.1.0), memória semântica com fonte, data e validade, e ações sugeridas (nunca executadas); código em `agente/`, testes em `tests/`. Na seção 5, o agente integrado (`agente/integrado.py`) junta tudo atrás da barreira, com auditor de verificação (`agente/auditor.py`), post-mortem `.md` a pedido (`agente/postmortem.py`) e avaliação (`agente/avaliacao.py`, `scripts/avaliar_langsmith.py`). O rastreamento do LangSmith fica desligado em todo o projeto (`LANGSMITH_TRACING=false`); a seção 5.6 o liga só no envio do dataset e do experimento, com `ENVIAR_LANGSMITH=1`, e uma recusa do LangSmith (429, cota) vira aviso. A interface web própria (FastAPI com front HTML, CSS e JavaScript em `app/`) roda com `uvicorn app.main:app --host 127.0.0.1 --port 8501` ou `docker compose up`, em http://127.0.0.1:8501. A seção 0 do notebook mostra o agente final e o índice da rubrica. O relatório técnico (PDF) não fica no repositório: é entregue pelo Moodle.

## Subir tudo com Docker (loja + agente)

O jeito mais rápido de ver o agente funcionando: um comando sobe a loja (`incident-shop`, que simula
os serviços e os incidentes) e o agente já conectados. Precisa de Docker e de uma chave da OpenAI.

```bash
git clone https://github.com/erato690/incident-agent.git
cd incident-agent
echo "OPENAI_API_KEY=sk-..." > .env      # ou exporte OPENAI_API_KEY no shell
docker compose -f docker-compose.completo.yml up --build
```

1. Espere aparecer o agente iniciado (a primeira vez constrói as duas imagens, alguns minutos).
2. Abra o chat em http://127.0.0.1:8501. A loja fica em http://127.0.0.1:8000 (`/docs` mostra a API).
3. Pergunte, por exemplo, "o que está acontecendo com os pedidos?". O agente investiga a loja ao vivo.
4. Para parar: `Ctrl+C` e `docker compose -f docker-compose.completo.yml down`.

A loja é construída direto do GitHub, sem precisar clonar o `incident-shop`. O incidente vem da
variável `CENARIO` (padrão `pool_esgotado`; também `rate_limit`, `gateway_fora`,
`banco_lento_com_deploy` e os outros cenários da loja), por exemplo:
`CENARIO=rate_limit docker compose -f docker-compose.completo.yml up --build`. Outras variáveis:
`AGENTE_PORTA`, `SHOP_PORTA` e `SHOP_CONTEXTO` (caminho de um clone local da loja). As portas ficam
só em 127.0.0.1.

**Só o agente, com os dados gravados** (sem a loja): `docker compose up --build`. Sem a variável
`LOJA_URL`, o agente lê `dados_dummy/cenarios/`. Sem chave da OpenAI, o notebook roda e pula as
células que chamam o modelo.

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
- **Loja e agente juntos (Docker)**: veja a seção "Subir tudo com Docker" acima.
- **Avaliação**: `python scripts/avaliar_langsmith.py` roda os 8 cenários localmente (com a chave do modelo) e imprime as métricas; `--enviar` publica o dataset e o experimento no LangSmith (precisa de `LANGSMITH_API_KEY` e de cota).
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
- **Auditor de verificação cognitiva**: valida se as conclusões do agente são consistentes com as evidências, com as técnicas vistas na disciplina: extração das afirmações com Pydantic (`with_structured_output`), checagem de fatos determinística (`checar_fatos`, métrica `fato_deterministico`), inferência lógica (NLI) com veredito explícito `apoia`, `refuta` ou `neutra` e falácias do domínio (métrica `veredito_nli`), e avaliação da trajetória (`trajetoria_ferramentas`, em código, sem modelo). Duas técnicas rodam em código e duas usam o modelo; a numeração não é a ordem de execução. Uma trava final em código (`veredito_final`) rebaixa o veredito do juiz quando ele contradiz a checagem de fatos.
- **Relatório**: gerado em `.md` só quando o engenheiro pede; internamente tudo é JSON (formato de dados em texto).
- **Sem execução de ações**: o agente não executa correções, apenas as sugere.
- **Modelo de linguagem (LLM) de chat**: escolha explícita entre DeepSeek (`ChatDeepSeek`) e OpenAI (`ChatOpenAI("gpt-4o-mini")`) por `LLM_PROVEDOR` (padrão `openai`), sem troca automática. Embeddings: OpenAI `text-embedding-3-small`.
- **Fonte de dados**: lê a variável `LOJA_URL` (API do repositório irmão `incident-shop`, ao vivo); sem ela, lê respostas gravadas em `dados_dummy/cenarios/`.
- **Ferramenta real de API externa**: GitHub, função `comparar_versoes` (compara duas tags/commits do repositório `incident-shop` via API REST real do GitHub, funciona sem token).
- **Telas (interface web própria, FastAPI com HTML, CSS e JavaScript sem build)**: uso (conversa por incidente, com barra lateral de sessões) e análise (trajetória + auditor).
- **Guardrails**: seis camadas (máscara local e moderação, compreensão, ferramentas, dados que voltam, saída, análise); sem tool de escrita; SQL somente leitura.
- **Deploy**: Docker local via `docker compose`. A porta vem da variável `PORT`, o que permite hospedar em plataformas como o Railway; o deploy em nuvem não foi feito.

## Prazo

Entrega: 13/11/2026.
