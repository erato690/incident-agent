---
titulo: Runbook: vazamento de memória e OOMKilled
tipo: runbook
servico: todos
assunto: vazamento de memória
---

# Runbook: vazamento de memória e OOMKilled

## Sintomas
- Contêiner reiniciado com motivo OOMKilled.
- Uso de memória sobe de forma contínua até o limite e cai com a reinicialização.
- Contador de reinícios crescente e latência instável.

## Diagnóstico
1. Observe a métrica de memória: crescimento linear sem queda indica vazamento.
2. Verifique os reinícios e o motivo no log do orquestrador.
3. Compare com o último deploy, pois o vazamento costuma começar numa versão nova.

## Ações (sugestões, nunca executar sem aprovação do engenheiro)
- Fazer rollback para a versão anterior se o vazamento começou com um deploy.
- Aumentar temporariamente o limite de memória.
- Capturar um heap dump para análise.
