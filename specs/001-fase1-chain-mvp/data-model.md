# Data Model: Fase 1

Todos os modelos são Pydantic v2 em `agente/schemas.py` (princípio VIII). Numeração das trocas
JSON segue o princípio VIII da constitution.

## EntradaTurno

| Campo | Tipo | Regra |
|---|---|---|
| `mensagem` | `str` | texto livre do engenheiro; pode ser vazio |
| `historico` | `list[BaseMessage]` | mensagens anteriores da conversa; padrão `[]` |

## ResultadoModeracao (troca 1)

| Campo | Tipo | Regra |
|---|---|---|
| `status` | `Literal["ok", "sinalizada", "pulada"]` | |
| `categorias` | `list[str]` | categorias sinalizadas; vazio se `ok` ou `pulada` |
| `motivo` | `str \| None` | preenchido quando `pulada` (sem chave, sem rede, erro) |

## AnaliseNLU (troca 2)

| Campo | Tipo | Regra |
|---|---|---|
| `intencao` | `Literal[...]` | `investigar_erro`, `checar_deploy`, `checar_metrica`, `comparar_incidente`, `pedir_runbook`, `gerar_relatorio`, `confirmar_causa`, `saudacao`, `fora_do_escopo`, `conteudo_proibido`, `pedido_de_acao`, `tentativa_de_injecao` |
| `servico` | `str \| None` | herdado do histórico quando a pergunta não cita |
| `ambiente` | `str \| None` | |
| `janela_tempo` | `str \| None` | |
| `erro_texto` | `str \| None` | trecho do erro citado na mensagem |
| `dado_faltante` | `str \| None` | o que falta para investigar |

## ImpressaoDigital e ErroPreprocessado

| Campo | Tipo | Regra |
|---|---|---|
| `excecao` | `str \| None` | primeira linha de exceção encontrada |
| `primeiro_frame` | `str \| None` | primeiro frame que não é de biblioteca |
| `servico` | `str \| None` | do NLU ou de nome conhecido no texto |
| `texto_limpo` | `str` | sem frames repetidos, no máximo 4.000 caracteres, já mascarado |

`ErroPreprocessado` = `impressao: ImpressaoDigital` (campos `excecao`, `primeiro_frame`,
`servico`) + `texto_limpo` (aninhado, como implementado).

## AnaliseIncidente (troca 3)

| Campo | Tipo | Regra |
|---|---|---|
| `severidade` | `Literal["baixa", "media", "alta", "critica"]` | |
| `categoria` | `str` | ex.: `null_pointer`, `timeout`, `capacidade`, `configuracao` |
| `servico` | `str \| None` | |
| `resumo` | `str` | até ~300 caracteres |
| `hipoteses` | `list[Hipotese]` | ordenadas por `confianca` decrescente; pode ser vazia só com `evidencia_insuficiente=True` |
| `evidencia_insuficiente` | `bool` | `True` quando falta dado (princípio II) |
| `proximos_passos` | `list[str]` | ao menos 1 item |

**Hipotese**: `causa: str`, `confianca: float` (0 a 1), `evidencia: str` (trecho literal do
texto de entrada; validação: não vazio).

## RespostaFixa

| Campo | Tipo | Regra |
|---|---|---|
| `texto` | `str` | gerado por `PromptTemplate` por categoria |
| `camada` | `Literal[1, 2]` | 1 = moderação, 2 = NLU |
| `categoria` | `str` | categoria da moderação ou intenção do NLU |

## RespostaTurno (saída do pipeline; base da troca 5 nas fases seguintes)

| Campo | Tipo | Regra |
|---|---|---|
| `rota` | `Literal["fixa", "investigacao", "erro"]` | |
| `moderacao` | `ResultadoModeracao` | |
| `nlu` | `AnaliseNLU \| None` | `None` quando a moderação sinalizou ou a mensagem é vazia |
| `fixa` | `RespostaFixa \| None` | preenchido quando `rota="fixa"` |
| `analise` | `AnaliseIncidente \| None` | preenchido quando `rota="investigacao"` |
| `erro` | `str \| None` | JSON inválido após a nova tentativa |

## Fluxo de estados de um turno

```text
mensagem ─▶ máscara ─▶ vazia? ──sim──▶ fixa (camada 2, "vazia")
                         │não
                         ▼
                     moderação ── sinalizada ──▶ fixa (camada 1)
                         │ok / pulada
                         ▼
                        NLU ── guardrail / saudação / fora do escopo / fase futura ──▶ fixa (camada 2)
                         │investigação
                         ▼
                  pré-processamento ─▶ investigação ─▶ JSON válido ─▶ investigacao
                                                      └ inválido 2x ─▶ erro
```
