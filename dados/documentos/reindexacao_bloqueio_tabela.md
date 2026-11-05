---
titulo: Runbook: reindexação e bloqueio de tabela no db-principal
tipo: runbook
servico: db-principal
assunto: bloqueio de tabela
---

# Runbook: reindexação e bloqueio de tabela no db-principal

## Sintomas
- Mensagens de lock wait timeout e statement timeout nos logs dos serviços que usam o db-principal.
- Latência alta nas escritas de uma tabela específica, enquanto as demais seguem normais.
- Sessões aguardando bloqueio nas estatísticas do banco.
- Manutenção em andamento, como REINDEX, na tabela afetada.

## Diagnóstico
1. Consulte as estatísticas do banco e verifique bloqueios aguardando e manutenção em andamento.
2. Confirme se há um REINDEX ou VACUUM FULL rodando na tabela citada nos logs.
3. Compare o horário do início do incidente com o horário da manutenção. Se coincidem, a manutenção é a causa raiz, não um deploy.
4. Consulte a política de manutenção do db-principal para saber a janela permitida.

## Ações (sugestões, nunca executar sem aprovação do engenheiro)
- Reagendar o REINDEX para a janela de manutenção, entre 02h e 04h.
- Usar REINDEX CONCURRENTLY nas próximas execuções, para não bloquear a escrita.
- Se o impacto for crítico, pedir a aprovação para interromper a manutenção em andamento.
