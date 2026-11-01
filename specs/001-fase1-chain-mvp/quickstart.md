# Quickstart: validar a Fase 1

## Pré-requisitos

- Python 3.11+ e o repositório clonado.
- `.env` com `DEEPSEEK_API_KEY` (ou `OPENAI_API_KEY` + `FORCAR_PLANO_B=1`). `OPENAI_API_KEY` é
  opcional para a moderação.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 1. Testes determinísticos

```bash
pytest tests/ -q
```

Esperado: máscara, pré-processamento, schemas e roteamento (com NLU falso) passam.

## 2. Seção 1 do notebook

```bash
jupyter nbconvert --to notebook --execute projeto.ipynb --output /tmp/projeto_exec.ipynb
```

Esperado (SC-001 a SC-005):

- célula de setup imprime o modelo escolhido;
- sem `OPENAI_API_KEY`: aviso único "moderação pulada";
- `invoke` com o cenário `deploy_com_bug` devolve `AnaliseIncidente` válida com hipótese e
  evidência citada;
- `batch` processa todas as mensagens de erro dos cenários;
- `stream` mostra o JSON crescendo;
- célula `@chain` imprime `True` na comparação com a versão no pipe;
- tabela da bateria: rota obtida = rota esperada em todas as linhas; nenhum `[SEGREDO]`
  original aparece no texto enviado;
- tabela final liga cada item da rubrica da Fase 1 à célula que o comprova.

## 3. Sem chave da OpenAI e sem `LOJA_URL`

Rodar de novo com `OPENAI_API_KEY` vazia: a seção deve terminar sem erro (FR-002, FR-015).
