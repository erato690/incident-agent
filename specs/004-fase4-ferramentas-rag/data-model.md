# Data Model: Fase 4

## Novos (Pydantic, `agente/schemas.py`)

### `AcaoSugerida`
| Campo | Tipo | Regra |
|---|---|---|
| acao | str | imperativo curto ("reagendar o REINDEX para a janela de manutenção") |
| motivo | str | liga a ação ao diagnóstico |
| risco | Literal["baixo","medio","alto"] | |
| runbook | str \| None | título do runbook de origem |
| status | Literal["sugerida (não executada)"] | fixo; nunca outro valor |

### `ListaAcoes`
`acoes: list[AcaoSugerida]` (1 a 3); saída estruturada do LLM dentro de `sugerir_acao`.

### `EstatisticaTabela` (contrato `contracts/estatisticas_banco.md`)
tabela, servicos (list[str]), varreduras_sequenciais, varreduras_por_indice,
reindexacao_em_andamento (bool), operacao_em_andamento (str | None), ultimo_analyze,
inchaco_indice_pct (float). Envelope: `consulta` (cenario, servico, momento), `banco`, `tabelas`.
Usado só no resumo da ferramenta (o JSON vem da loja).

## Alterados

- `AnaliseIncidente.acoes_sugeridas: list[AcaoSugerida] = []` (default vazio; Fases 1 a 3
  inalteradas; preenchido pelo pipeline a partir do contexto, não pelo modelo).
- `Intencao` + `"confirmar_fato"`.
- `ContextoTurno` + `acoes_sugeridas: list[AcaoSugerida]`, `fato_gravado: FatoSemantico | None`.
- `RespostaTurno` + `fato: FatoSemantico | None` (rota "memoria" na confirmação de fato).

## SQLite `dados/incidentes.db` (D3)

| Tabela | Colunas |
|---|---|
| servicos | nome PK, time, linguagem, banco (nullable), dependencia_externa (nullable) |
| deploys | id PK, servico FK, versao, horario (ISO), autor, mudanca |
| incidentes | id PK, servico FK, inicio (ISO), fim (ISO), severidade, categoria, causa, cenario (nullable) |

Conteúdo: os 4 serviços; os deploys das tags do incident-shop; os 8 cenários como incidentes
de outubro de 2026 mais ~16 incidentes históricos fictícios (jan–set 2026), determinísticos.

## Corpus `dados/documentos/*.md`

Cabeçalho YAML simples por arquivo: `titulo`, `tipo` (runbook | documentacao), `servico`
(ou `todos`), `assunto` (ex.: "PagaFácil"). 8 runbooks (um por tipo de falha dos cenários) + 2
documentos (limites do PagaFácil; política de manutenção do db-principal).

## Fato semântico (já existe)

Gravado com `fonte="documentacao"` (D6, validade 90 dias) ou `fonte="usuario"` (D7, após
`confirmar_fato`). Texto mascarado antes de gravar.
