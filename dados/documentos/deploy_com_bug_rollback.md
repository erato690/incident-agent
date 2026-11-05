---
titulo: Runbook: deploy com bug e NullPointerException
tipo: runbook
servico: todos
assunto: deploy com defeito
---

# Runbook: deploy com bug e NullPointerException

## Sintomas
- Aumento de erros 5xx logo após um deploy.
- NullPointerException repetida nos logs, sempre no mesmo trecho de código.
- A taxa de erro estava normal antes do horário do deploy.

## Diagnóstico
1. Liste os deploys do serviço e compare o horário com o início dos erros.
2. Compare as versões (commits e arquivos alterados) para achar a mudança suspeita.
3. Confirme que o stack trace aponta para o código alterado.

## Ações (sugestões, nunca executar sem aprovação do engenheiro)
- Fazer rollback para a versão anterior.
- Abrir correção com teste cobrindo o caso nulo.
- Revisar o processo de revisão do código alterado.
