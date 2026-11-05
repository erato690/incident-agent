---
titulo: Runbook: gateway externo indisponível
tipo: runbook
servico: pagamentos-api
assunto: indisponibilidade de provedor
---

# Runbook: gateway externo indisponível

## Sintomas
- Respostas HTTP 503 do gateway externo de pagamentos.
- Falhas em todas as chamadas ao provedor, sem relação com o volume de requisições.
- A página de status do provedor informa instabilidade.

## Diagnóstico
1. Confirme que o 503 vem do provedor e não do nosso serviço.
2. Consulte a página de status do provedor e o histórico de incidentes dele.
3. Verifique se o disjuntor (circuit breaker) abriu e se há filas acumulando.

## Ações (sugestões, nunca executar sem aprovação do engenheiro)
- Acionar o contato de suporte do provedor.
- Ativar o modo degradado: enfileirar pagamentos para processar depois.
- Comunicar o time de produto sobre o impacto.
