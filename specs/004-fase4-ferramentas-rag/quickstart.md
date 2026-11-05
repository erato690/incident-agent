# Quickstart: Fase 4

1. `.venv/bin/pytest -q` (sem chave, sem rede) e `.venv/bin/ruff check . && .venv/bin/ruff format --check .`
2. `.venv/bin/python scripts/construir_sqlite.py` (sem chave) e `bash -ic ".venv/bin/python scripts/construir_indice.py"` (com a chave; embeddings).
3. Notebook: seção 4 roda sozinha; com a chave, bateria `fase4_mensagens.json` com causa certa em 8/8, DROP recusado, falha de recuperação antes/depois, três caminhos da wiki, ações "sugerida (não executada)".
4. Contrato do shop: [contracts/estatisticas_banco.md](contracts/estatisticas_banco.md). Sem shop no ar, as ferramentas usam `dados_dummy/cenarios/*.json`.
