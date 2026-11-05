---
titulo: Runbook: pool de conexões esgotado
tipo: runbook
servico: pedidos-api
assunto: pool de conexões
---

# Runbook: pool de conexões esgotado

## Sintomas
- Erros de timeout ao obter conexão do pool (connection pool exhausted).
- O número de conexões em uso fica no máximo configurado do pool por vários minutos.
- Requisições de escrita e leitura aguardam uma conexão livre e falham após o tempo limite.
- Costuma aparecer depois de um pico de tráfego ou de uma consulta que segura a conexão por muito tempo.

## Diagnóstico
1. Compare a métrica de conexões do banco com o tamanho máximo do pool.
2. Procure nos logs a mensagem de timeout ao obter conexão e identifique o endpoint que mais consome.
3. Verifique se houve pico de tráfego ou deploy que alterou o uso do pool.
4. Confira se há conexões vazadas (abertas e nunca devolvidas ao pool).

## Ações (sugestões, nunca executar sem aprovação do engenheiro)
- Aumentar o tamanho do pool de forma moderada, respeitando o limite de conexões do banco.
- Corrigir o código que não devolve a conexão ao pool.
- Reduzir o tempo máximo das consultas longas.
- Escalar horizontalmente o serviço se o pico de tráfego for legítimo.
