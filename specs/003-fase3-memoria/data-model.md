# Data Model: Fase 3

## Sessao (curto prazo)

Todos os modelos desta página ficam em `agente/schemas.py`.

| Campo | Tipo | Regra |
|---|---|---|
| `thread_id` | `str` | `str(uuid4())` gerado em `abrir_sessao` |
| `criada_em` | `datetime` | relógio injetável |
| `servico` | `str \| None` | atualizado com o serviço do NLU quando aparece |
| `cenario` | `str \| None` | configuração (não vai ao modelo) |
| `turnos` | `int` | incrementa a cada turno |

Estado do grafo de conversa: `mensagens: Annotated[list[BaseMessage], add_messages]`,
`resumo: str`, `sessao: Sessao`, `resposta: RespostaTurno | None`.

## Episodio (episódica)

| Campo | Tipo | Regra |
|---|---|---|
| `id_memoria` | `str` | `uuid4` do episódio; chave no namespace `("episodica", servico)` |
| `incidente_id` | `str` | incidente a que o episódio se refere |
| `thread_id` | `str` | sessão de origem da confirmação |
| `servico` | `str` | obrigatório |
| `resumo` | `str` | sintoma relatado + o que a investigação viu, mascarado |
| `causa` | `str` | causa confirmada, mascarada |
| `evidencia` | `str \| None` | citada pelo engenheiro |
| `origem` | `Literal["agente", "engenheiro"]` | causa levantada pelo agente ou só informada |
| `criado_em` | `datetime` | data do episódio |
| `status` | `Literal["ativo", "arquivado"]` | a busca só devolve `ativo` |
| `substitui` | `str \| None` | `id_memoria` do episódio arquivado por este |
| `motivo_registro` | `str \| None` | motivo da resolução de memória (auditoria) |
| `acessos` | `int` | começa em 0; soma 1 a cada recuperação |

Texto indexado no store (`texto`): resumo + serviço + causa + evidência.

`ResolucaoMemoria` (saída do LLM resolvedor): `acao: Literal["inserir_novo",
"atualizar_existente"]`, `id_memoria_antiga: str | None`, `motivo: str`.

`ResultadoRegistro`: `decisao: ResolucaoMemoria`, `episodio: Episodio` (novo, ativo),
`arquivado: Episodio | None`.

`EpisodioEncontrado`: `episodio`, `similaridade`, `dias`, `acessos`, `pontuacao` =
`0,7 * similaridade + 0,2 * 1/(1 + 0,05 * dias) + min(0,15; 0,01 * acessos)`.

## FatoSemantico (semântica, só interface)

| Campo | Tipo | Regra |
|---|---|---|
| `assunto` | `str` | produto ou serviço; namespace `("semantica", assunto)` |
| `fato` | `str` | ex.: "API do GitHub sem token: 60 chamadas por hora" |
| `fonte` | `Literal["documentacao", "usuario", "incidente"]` | |
| `verificado_em` | `datetime` | |
| `valido_ate` | `datetime \| None` | `None` = sem validade |

`FatoSemanticoEncontrado` (achatado): `fato`, `fonte`, `verificado_em`, `valido_ate`,
`similaridade`, `vencido: bool`.

## AvaliacaoRelevancia (curto prazo)

`nivel: Literal["baixa", "alta", "critica"]`, `motivo: str`. Guardada em
`additional_kwargs` de cada mensagem; `baixa` não vai ao contexto.

## ContextoTurno (trava das ferramentas de memória)

`intencao`, `servico`, `incidente_id`, `thread_id` (do estado do turno) e `registro:
ResultadoRegistro | None` (preenchido por `gravar_episodio`).

## CausaConfirmada (argumentos de `gravar_episodio`)

`resumo: str`, `causa: str`, `evidencia: str | None`, `levantada_pelo_agente: bool`. O serviço e
o incidente vêm do `ContextoTurno`.

## RespostaTurno (alterações)

- `rota`: acrescenta `"memoria"`. Sem serviço ou sem `incidente_id`: rota `"fixa"` com
  `pedir_servico` ou `pedir_incidente`; falha do agente de registro: rota `"erro"`.
- `episodio: Episodio | None` (registrado ou atualizado neste turno).
- `episodio_anterior: Episodio | None` (episódio arquivado pela resolução, se houve).
- `resolucao: ResolucaoMemoria | None` (decisão e motivo, para auditoria).
- Consultas à memória aparecem na `trajetoria` (`ferramenta == "consultar_memoria"`).
