---
titulo: Runbook: variável de ambiente faltando
tipo: runbook
servico: todos
assunto: configuração
---

# Runbook: variável de ambiente faltando

## Sintomas
- O serviço não sobe após um deploy e entra em loop de reinicialização.
- Mensagens como missing required environment variable ou configuração obrigatória ausente.

## Diagnóstico
1. Leia o log de inicialização e identifique o nome da variável.
2. Compare a configuração do ambiente com a da versão anterior.
3. Verifique se o deploy introduziu uma configuração nova.

## Ações (sugestões, nunca executar sem aprovação do engenheiro)
- Cadastrar a variável no ambiente e reiniciar o serviço.
- Se não houver o valor correto, fazer rollback para a versão anterior.
- Adicionar validação da configuração no pipeline de deploy.
