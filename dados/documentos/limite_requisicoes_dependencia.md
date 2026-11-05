---
titulo: Runbook: limite de requisições de dependência externa
tipo: runbook
servico: todos
assunto: limite de requisições
---

# Runbook: limite de requisições de dependência externa

## Sintomas
- Respostas HTTP 429 (Too Many Requests) vindas de um provedor externo.
- Cabeçalho Retry-After nas respostas e aumento de falhas nas chamadas ao provedor.
- Volume de requisições por minuto acima do limite contratado.

## Diagnóstico
1. Identifique o provedor nos logs e consulte o limite documentado do plano contratado.
2. Compare o volume de requisições por minuto com o limite.
3. Verifique se houve repetição automática de chamadas sem espera, o que agrava o problema.

## Ações (sugestões, nunca executar sem aprovação do engenheiro)
- Respeitar o Retry-After e aplicar backoff exponencial nas tentativas.
- Colocar as chamadas em uma fila para suavizar o pico.
- Pedir ao provedor o aumento de cota ou migrar para um plano maior.
