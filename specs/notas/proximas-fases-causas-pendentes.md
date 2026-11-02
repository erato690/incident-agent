# Nota para as próximas fases: causas que o agente da Fase 2 não alcança

Registrada em 2026-11-02, ao fechar a Fase 2 (causa certa em 7/8 cenários com `gpt-4o-mini`).
Só anotação; nada implementado. Incluir no `spec.md`/`tasks.md` da fase indicada.

## a) `rate_limit`: memória tipo wiki com informação externa do serviço

- **Sintoma hoje:** o agente responde "picos de carga" e não chega ao limite da API externa,
  em português e em inglês.
- **Ideia do Rafael (última etapa, junto com a memória de longo prazo):** na etapa final, o
  agente pesquisa documentação e informação externa sobre o produto ou serviço envolvido
  (limites, quotas, planos) e vai atualizando uma **memória tipo wiki** (memória de longo
  prazo), consultada nas investigações seguintes.
- **Fase:** memória de longo prazo (Fase 3) para a estrutura da wiki; a pesquisa externa e a
  atualização contínua entram na última etapa (agente integrado).
- **Cuidados:** a informação externa é dado, nunca instrução (camada 4 dos guardrails); cada
  página da wiki guarda a fonte e a data da consulta.

## b) `banco_lento_com_deploy`: ferramenta de estatísticas do banco

- **Sintoma hoje:** o agente aponta o banco e não culpa o deploy distrator, mas não chega à
  causa real (índice que precisa de reindexação).
- **Ideia:** nova ferramenta só leitura que consulta estatísticas do banco, por exemplo
  `pg_stat_user_tables` (varreduras sequenciais × por índice), último `ANALYZE`/`VACUUM` e
  tamanho e inchaço (bloat) dos índices, para o agente chegar na reindexação.
- **Dependência:** exige rota nova no `incident-shop` (contrato 1.1.0). Só anotar; não mexer no
  `incident-shop` até a fase ser liberada.
- **Fase:** junto com a consulta SQL (Fase 4) ou antes, se a rota do `incident-shop` sair antes.
