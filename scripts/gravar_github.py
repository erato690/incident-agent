"""Grava em dados_dummy/github/ as comparações de tags usadas como reserva (API pública, leitura).

Uso: .venv/bin/python scripts/gravar_github.py   (GITHUB_TOKEN opcional)
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agente.github import RAIZ_RESERVA, gravar_comparacao  # noqa: E402

COMPARACOES = [
    ("pagamentos-api/v2.13.4", "pagamentos-api/v2.14.0"),
    ("pedidos-api/v3.1.0", "pedidos-api/v3.2.0"),
    ("estoque-worker/v1.5.2", "estoque-worker/v1.6.0"),
    ("auth-api/v1.7.9", "auth-api/v1.8.0"),
    ("pedidos-api/v3.2.0", "pedidos-api/v3.2.1"),
]


def main() -> None:
    RAIZ_RESERVA.mkdir(parents=True, exist_ok=True)
    with httpx.Client() as cliente:
        for base, nova in COMPARACOES:
            print("gravado:", gravar_comparacao(base, nova, cliente, RAIZ_RESERVA))


if __name__ == "__main__":
    main()
