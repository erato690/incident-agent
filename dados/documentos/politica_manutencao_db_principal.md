---
titulo: Política de manutenção do db-principal
tipo: documentacao
servico: db-principal
assunto: manutenção do banco
---

# Política de manutenção do db-principal

## Janela de manutenção
- Operações de manutenção do banco só podem rodar na janela entre 02h e 04h.
- Isso vale para REINDEX, VACUUM FULL e qualquer operação que trave a tabela.

## Cuidados
- O REINDEX trava a escrita na tabela enquanto roda.
- Fora da janela, use REINDEX CONCURRENTLY e peça aprovação ao time de banco de dados.
- Manutenção fora da janela deve ser registrada e comunicada no canal de plantão.
