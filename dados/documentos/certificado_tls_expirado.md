---
titulo: Runbook: certificado TLS expirado
tipo: runbook
servico: todos
assunto: certificado TLS
---

# Runbook: certificado TLS expirado

## Sintomas
- Erros de handshake TLS e mensagens de certificate expired nos logs.
- Clientes recusam a conexão HTTPS; chamadas entre serviços falham de uma vez, a partir de um horário exato.

## Diagnóstico
1. Verifique a data de validade do certificado do serviço ou do provedor citado no erro.
2. Confirme se a renovação automática falhou.
3. Compare o horário do primeiro erro com a data de expiração.

## Ações (sugestões, nunca executar sem aprovação do engenheiro)
- Renovar o certificado e recarregar o serviço.
- Corrigir a automação de renovação.
- Criar um alerta de expiração com 30 dias de antecedência.
