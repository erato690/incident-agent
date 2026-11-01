# Contrato: pipeline da Fase 1

Interface que as fases seguintes, o `app/` e a bateria de testes usam. Tipos em
[data-model.md](../data-model.md).

## `pipeline_fase1: Runnable[dict, RespostaTurno]`

- **Entrada**: `{"mensagem": str, "historico": list[BaseMessage]}` (`historico` opcional).
- **Saída**: `RespostaTurno`.
- **Métodos garantidos**: `invoke`, `batch`, `stream` (interface Runnable).
- **Garantias**:
  - nenhum texto não mascarado sai para a moderação ou para o LLM (FR-000);
  - `rota="fixa"` nunca chama o LLM de investigação (FR-001, FR-005);
  - falha da moderação nunca levanta exceção (FR-002);
  - JSON inválido após uma nova tentativa vira `rota="erro"`, sem exceção (edge case).

## Funções determinísticas (`agente/`)

| Função | Assinatura | Contrato |
|---|---|---|
| `mascarar` | `(texto: str) -> str` | substitui segredos e PII por `[SEGREDO]`, `[EMAIL]`, `[CPF]`, `[CARTAO]`; idempotente |
| `preprocessar` | `(texto: str, servico: str \| None = None) -> ErroPreprocessado` | remove ruído, limita a 4.000 caracteres, extrai impressão digital |
| `moderar` | `(texto: str) -> ResultadoModeracao` | nunca levanta exceção |
| `escolher_llm` | `() -> BaseChatModel` | DeepSeek ou plano B conforme env; imprime o escolhido |

## Mensagens de teste (`dados_dummy/fase1_mensagens.json`)

```json
[{"id": "deploy_com_bug", "mensagem": "...", "rota_esperada": "investigacao",
  "intencao_esperada": "investigar_erro"}]
```

`rota_esperada` ∈ {`fixa`, `investigacao`}; `intencao_esperada` opcional.
