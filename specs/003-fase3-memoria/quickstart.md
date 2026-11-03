# Quickstart: Fase 3

1. Sem chave: `.venv/bin/pytest -q` (testes de memória, conversa, pipeline com memória e
   ferramenta) e `ruff check . && ruff format --check .`.
2. Notebook: rodar Setup e depois a seção 3 inteira. Sem chave, as células com modelo são puladas
   e aparecem as tabelas (CoALA, comparação de ferramentas), o diagrama e os testes.
3. Com a chave (`bash -ic` carrega a chave do `~/.bashrc`): a seção 3 mostra o chatbot clássico e o
   grafo com `MemorySaver`, a confirmação registrando o episódio, a troca de causa, a pergunta
   "já aconteceu antes?" citando o incidente anterior, a conversa longa com resumo e a bateria.
4. Esperado: SC-001 a SC-006 da spec; seções 1 e 2 com os mesmos resultados.
