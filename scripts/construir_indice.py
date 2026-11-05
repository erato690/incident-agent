"""Constrói o índice FAISS de dados/documentos/ (usa a chave da OpenAI para os embeddings).

Uso: python scripts/construir_indice.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from agente.memoria import embeddings_padrao  # noqa: E402
from agente.recuperacao import (  # noqa: E402
    PASTA_DOCUMENTOS,
    PASTA_INDICE,
    carregar_documentos,
    construir_indice,
    dividir,
)


def main() -> None:
    load_dotenv()
    construir_indice(embeddings_padrao(), PASTA_INDICE, PASTA_DOCUMENTOS)
    pedacos = len(dividir(carregar_documentos(PASTA_DOCUMENTOS)))
    print(f"Índice gravado em {PASTA_INDICE} ({pedacos} pedaços).")


if __name__ == "__main__":
    main()
