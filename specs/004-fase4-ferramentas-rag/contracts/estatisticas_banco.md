# Contrato: `GET /estatisticas_banco` (incident-shop 1.1.0)

Fonte da verdade: `incident-shop/docs/contrato-api.md`, seção "GET /estatisticas_banco". O contrato
real substituiu a proposta inicial do incident-agent (D2 A), que tinha `servico` obrigatório,
`coletado_em`, linhas vivas/mortas, vacuum e bloqueios. Esses campos não existem mais.

## Requisição

`GET /estatisticas_banco?cenario=<id>[&servico=<servico>]`

- `cenario` obrigatório: ausente `422`, desconhecido `404`.
- `servico` opcional (um dos 4 serviços); outro valor: `422`. Sem `servico`, todas as tabelas.
- Não há `inicio` nem `fim`: o retrato é de um instante (`sintoma_inicio` do cenário).

## Resposta 200

Tabelas na ordem fixa `pedidos`, `itens_pedido`, `estoque` (pedidos-api e estoque-worker),
`reservas_estoque`. `pagamentos-api` e `auth-api` não usam o `db-principal`: `tabelas: []`.

| Campo da tabela | Significado |
|---|---|
| `tabela`, `servicos` | Nome e serviços que a usam |
| `varreduras_sequenciais`, `varreduras_por_indice` | Leituras na última hora (inteiros) |
| `reindexacao_em_andamento` | `true` enquanto um `REINDEX` roda na tabela |
| `operacao_em_andamento` | Instrução em execução (ex.: `REINDEX TABLE estoque`) ou `null` |
| `ultimo_analyze` | Horário do último `ANALYZE` |
| `inchaco_indice_pct` | Percentual de índice inchado (1 casa decimal) |

```json
{
  "consulta": {"cenario": "banco_lento_com_deploy", "servico": "estoque-worker",
               "momento": "2026-10-08T15:47:00-03:00"},
  "banco": "db-principal",
  "tabelas": [
    {"tabela": "estoque", "servicos": ["pedidos-api", "estoque-worker"],
     "varreduras_sequenciais": 2248, "varreduras_por_indice": 38,
     "reindexacao_em_andamento": true, "operacao_em_andamento": "REINDEX TABLE estoque",
     "ultimo_analyze": "2026-10-08T03:00:00-03:00", "inchaco_indice_pct": 41.0}
  ]
}
```

Só `banco_lento_com_deploy` foge do estado saudável (tabela `estoque`, reindexação desde 15:40,
índice indisponível: varreduras por índice < 100 e sequenciais na casa dos milhares). Nos demais
cenários, inclusive `pool_esgotado`, o banco aparece saudável. Valores determinísticos.

## Gravação (`dados_dummy`)

`dados_dummy/cenarios/*.json` foi regravado com `scripts/gravar_dados_dummy.py` do incident-shop
(commits `3d424c8` e `89cb6a6`, sem push). A chave `"estatisticas_banco"` é o corpo da resposta
SEM `servico` (todas as tabelas). No modo gravado, `FonteLoja.estatisticas_banco(servico)` filtra
as tabelas cujo `servicos` contém o serviço e devolve o mesmo formato do contrato, com
`consulta.servico` preenchido. Sem a chave: `{"consulta": {...}, "banco": null, "tabelas": []}`.
