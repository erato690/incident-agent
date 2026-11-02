# Data Model: Fase 2

Reaproveita os modelos da Fase 1 (`specs/001-fase1-chain-mvp/data-model.md`): `AnaliseIncidente`,
`Hipotese` (com `evidencia_insuficiente` e `dado_que_falta`), `RespostaTurno`.

## CenarioConfigurado (configuração, nunca vai ao modelo)

| Campo | Tipo | Regra |
|---|---|---|
| `id` | `str` | um dos 8 cenários do `incident-shop` |
| `inicio`, `fim` | `datetime \| None` | janela do cenário (do `GET /cenarios` ao vivo ou do arquivo gravado) |

## PassoTrajetoria

| Campo | Tipo | Regra |
|---|---|---|
| `ferramenta` | `str` | nome da ferramenta |
| `argumentos` | `dict` | o que o modelo preencheu (nunca contém o cenário) |
| `duracao_ms` | `int` | ≥ 0 |
| `tamanho` | `int` | caracteres da observação |
| `erro` | `str \| None` | erro legível, se a ferramenta falhou |
| `reserva` | `bool` | `True` quando a resposta veio da gravação (GitHub) |

## ResultadoInvestigacao (saída do passo 6 na Fase 2)

| Campo | Tipo | Regra |
|---|---|---|
| `analise` | `AnaliseIncidente \| None` | presente quando o JSON validou |
| `erro` | `str \| None` | presente quando a nova tentativa e a reserva falharam |
| `trajetoria` | `list[PassoTrajetoria]` | na ordem das chamadas |

Exatamente um entre `analise` e `erro`.

## RespostaTurno (Fase 1, estendida)

Novo campo `trajetoria: list[PassoTrajetoria] = []` (vazio nas respostas fixas e na Fase 1).

## Resposta gravada de cenário (`dados_dummy/cenarios/<id>.json`)

Formato sugerido pelo contrato 1.0.0 do `incident-shop`, um corpo de resposta por chave:

- `cenario`: item de `GET /cenarios` (`id`, `titulo`, `servico`, `sintoma_inicio`, `janela`).
- `logs`: corpo de `GET /logs` (`consulta`, `total`, `truncado`, `logs[]` com `horario`,
  `servico`, `nivel`, `mensagem`).
- `metricas`: corpo de `GET /metricas` (`series[]` com `servico`, `metrica`, `unidade`,
  `resumo{min,max,media,ultimo}`, `pontos[]{horario,valor}`).
- `deploys`: corpo de `GET /deploys` (`deploys[]` com `horario`, `servico`, `versao`, `tag`,
  `commit`, `autor`, `mensagem`).

Gravar duas vezes gera arquivos idênticos (a API é determinística). O gabarito do cenário não
está nos arquivos.

## ComparacaoVersoes (resumo devolvido por `comparar_versoes`)

| Campo | Tipo | Regra |
|---|---|---|
| `base`, `nova` | `str` | tags `<servico>/vX.Y.Z` |
| `commits` | `list[{mensagem, autor, data}]` | |
| `arquivos` | `list[{nome, status, adicoes, remocoes, trecho}]` | `trecho` limitado |
| `reserva` | `bool` | veio da gravação |

## Mensagem e conversa de teste (Fase 2)

Campos da Fase 1 + `cenario` (configuração), `ferramentas_esperadas` (informativo) e
`causa_esperada` (gabarito para o relatório, nunca enviado ao modelo).
