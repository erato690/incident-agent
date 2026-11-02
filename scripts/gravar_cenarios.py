"""Grava `dados_dummy/cenarios/<id>.json` a partir da API do incident-shop (contrato 1.0.0).

Uso: python scripts/gravar_cenarios.py [--url http://localhost:8765] [--saida dados_dummy/cenarios]

Cada arquivo tem {"cenario", "logs", "metricas", "deploys"}: o item de GET /cenarios e os
corpos de GET /logs (limite=5000), /metricas e /deploys do cenário. A API é determinística,
então gravar duas vezes gera arquivos idênticos.
"""

import argparse
import json
import os
from pathlib import Path

import httpx

SAIDA_PADRAO = Path(__file__).resolve().parent.parent / "dados_dummy" / "cenarios"
URL_PADRAO = "http://localhost:8765"


def gravar(url: str, saida: Path, cliente: httpx.Client | None = None) -> list[Path]:
    """Grava um arquivo por cenário e devolve os caminhos."""
    cliente = cliente or httpx.Client(timeout=30.0)
    url = url.rstrip("/")

    def get(rota: str, **params) -> dict:
        resposta = cliente.get(f"{url}{rota}", params=params)
        resposta.raise_for_status()
        return resposta.json()

    saida.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for cenario in get("/cenarios")["cenarios"]:
        dados = {
            "cenario": cenario,
            "logs": get("/logs", cenario=cenario["id"], limite=5000),
            "metricas": get("/metricas", cenario=cenario["id"]),
            "deploys": get("/deploys", cenario=cenario["id"]),
        }
        caminho = saida / f"{cenario['id']}.json"
        caminho.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        caminhos.append(caminho)
    return caminhos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=os.environ.get("LOJA_URL", URL_PADRAO))
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    argumentos = parser.parse_args()
    for caminho in gravar(argumentos.url, argumentos.saida):
        print(f"{caminho} ({caminho.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
