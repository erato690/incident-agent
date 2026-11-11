# Implementation Plan: Fase 5

**Spec**: [spec.md](spec.md) | **Date**: 2026-11-05

## Summary

O Investigador da Fase 4 ganha `consultar_sql` e passa a ser o agente único. O pipeline ganha o
passo do auditor depois da investigação (`agente/auditor.py`). A intenção `gerar_relatorio`
passa a gerar o post-mortem (`agente/postmortem.py`). O registro de turnos (`RegistroTurno`)
alimenta o Streamlit (`app/app.py`). A avaliação sai de `agente/avaliacao.py`
(avaliadores + dataset) e de `scripts/avaliar_langsmith.py`. O notebook ganha a seção 5, as
seções renomeadas e a seção 0. O relatório sai de `relatório técnico (fora do repositório)`, gerado em PDF por
`gerador do PDF (fora do repositório)` (em `docs/`, ignorado pelo git, e numa cópia em `~/Downloads/`).

## Technical Context

- **Dependências novas:** `streamlit` (app) e um gerador de PDF em Python puro (`fpdf2` ou
  `markdown` + `xhtml2pdf`; nível 2).
- **Já instalado:** `langsmith` (vem como dependência do LangChain).
- **Testes:** sem chave, com fakes; o auditor com LLM falso e checagem de fatos real.
- **Constraints:**
  - O auditor não altera a análise, só acrescenta veredito e aviso.
  - O post-mortem só é gerado a pedido.
  - Nada é enviado ao LangSmith sem a confirmação do Rafael.

## Constitution Check

| Princípio | Como o plano cumpre |
|---|---|
| I. Só leitura | Único atuador: o post-mortem `.md` (VIII) |
| II. Evidência | O auditor checa as afirmações contra as observações |
| IV. Memória | Sem mudança |
| V. Padrões da aula | `create_agent` como padrão; clássico numa célula curta; auditor com `with_structured_output` |
| VIII. JSON | Veredito do auditor e `RegistroTurno` em Pydantic |
| X. Entrega | Streamlit com duas telas, Dockerfile e compose |

## Estrutura

```text
agente/auditor.py      # Afirmacao, ListaAfirmacoes, VereditoCoerencia, Auditoria, checar_fatos, montar_auditor
agente/postmortem.py   # DadosPostMortem, gerar_postmortem (template)
agente/registro.py     # RegistroTurno, Registro (lista em memória + JSON)
agente/avaliacao.py    # exemplos do dataset, avaliadores (causa, trajetória, auditor), alvo
agente/integrado.py    # montar_agente_integrado (pipeline + todas as ferramentas + auditor + sessão)
app/app.py             # Streamlit: abas Uso e Análise
Dockerfile, docker-compose.yml
scripts/avaliar_langsmith.py, gerador do PDF (fora do repositório)
relatório técnico (fora do repositório)
```
