# Quickstart: validar a Fase 2

## Pré-requisitos

- Ambiente da Fase 1 (`README.md`, "Como rodar") + `pip install -r requirements.txt`
  (inclui `langchain-classic`).
- Opcional: `LOJA_URL` apontando para o `incident-shop` ao vivo; `GITHUB_TOKEN` para subir o
  limite do GitHub.

## 1. Testes

```bash
pytest -q
```

Esperado: testes da Fase 1 + loja, GitHub, ferramentas, agente (modelo falso), chains e bateria,
sem chave e sem rede.

## 2. Seção 2 do notebook

```bash
jupyter nbconvert --to notebook --execute --inplace projeto.ipynb
```

Esperado:

- `deploy_com_bug`: trajetória com logs, deploys e `comparar_versoes`
  (`pagamentos-api/v2.13.4...v2.14.0`); hipótese principal cita a `NullPointerException` e o
  cupom.
- `banco_lento_com_deploy`: o deploy `pedidos-api/v3.2.1` não é a hipótese principal; o
  raciocínio aparece.
- Barreira: respostas fixas sem nenhuma ferramenta na trajetória.
- Composições (sequencial, paralela, roteamento) e agente clássico com o ciclo impresso.
- Bateria e conversas com placar; causa principal correta em pelo menos 6 dos 8 cenários.
- Tempo total da seção 2 abaixo de 5 minutos.

## 3. Sem rede e sem chave

- Sem `LOJA_URL`: respostas gravadas.
- Sem rede: `comparar_versoes` usa a reserva e diz isso na observação.
- Sem chave do modelo: células com `%%requer_llm` puladas; o notebook termina.
