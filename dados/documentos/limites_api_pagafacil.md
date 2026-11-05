---
titulo: Limites da API do PagaFácil
tipo: documentacao
servico: pagamentos-api
assunto: PagaFácil
---

# Limites da API do PagaFácil

## Limite de requisições
- A API do PagaFácil aceita 100 requisições por minuto por conta.
- Acima disso, a API responde HTTP 429 (Too Many Requests).
- As respostas trazem o cabeçalho X-RateLimit-Limit com o limite da conta.
- As respostas 429 trazem o cabeçalho Retry-After: 30, ou seja, aguarde 30 segundos antes de tentar de novo.

## Planos
- O plano Empresarial permite 500 requisições por minuto.
- Para trocar de plano ou aumentar a cota, o pedido é feito ao suporte do PagaFácil.
