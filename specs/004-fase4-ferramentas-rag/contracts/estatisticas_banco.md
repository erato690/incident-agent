# Contrato: `GET /estatisticas_banco` (incident-shop 1.1.0)

Proposta do incident-agent (D2 A). Acréscimo compatível: `VERSAO_CONTRATO = "1.1.0"`.

## Requisição

`GET /estatisticas_banco?cenario=<id>&servico=<servico>`

- `cenario` (obrigatório, como nas outras rotas) e `servico` (obrigatório, um dos 4 serviços).
- Serviço sem banco ou cenário sem dado de banco: `200` com `tabelas: []`.
- Cenário inexistente: `404`, igual às outras rotas. Serviço inválido: `422`.

## Resposta 200

```json
{
  "cenario": "banco_lento_com_deploy",
  "servico": "pedidos-api",
  "banco": "db-principal",
  "coletado_em": "2026-10-08T15:50:00-03:00",
  "tabelas": [
    {
      "tabela": "estoque",
      "varreduras_sequenciais": 1830,
      "varreduras_por_indice": 12,
      "linhas_vivas": 48210,
      "linhas_mortas": 310,
      "ultimo_analyze": "2026-10-08T03:00:00-03:00",
      "ultimo_vacuum": "2026-10-08T03:00:00-03:00",
      "inchaco_indices_pct": 4.5,
      "bloqueios_aguardando": 37,
      "manutencao_em_andamento": "REINDEX TABLE estoque (iniciado 15:44)"
    }
  ]
}
```

- Campos espelham `pg_stat_user_tables` + `pg_locks` + `pg_stat_activity`, simplificados.
- `manutencao_em_andamento`: texto ou `null`. É o sinal da causa no `banco_lento_com_deploy`.
- Nos outros cenários com banco (ex.: `pool_esgotado`), valores normais e `manutencao_em_andamento: null`.
- Determinístico por cenário (mesma resposta a cada chamada), como logs e métricas.

## Gravação (`dados_dummy`)

O JSON gravado por cenário ganha a chave `"estatisticas_banco": [<corpo da resposta por serviço>]`
(lista com um item por serviço que tem banco). O agente filtra por `servico` no modo gravado.
