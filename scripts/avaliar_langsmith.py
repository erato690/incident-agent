"""Avalia o agente nos cenários: local por padrão; `--enviar` publica no LangSmith.

Uso: .venv/bin/python scripts/avaliar_langsmith.py [--enviar] [--prefixo fase5]
"""

import argparse
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from agente.avaliacao import (  # noqa: E402
    avaliar_localmente,
    enviar_ao_langsmith,
    exemplos_dataset,
    resumo_metricas,
)


def montar_alvo() -> Callable[[dict], object]:
    """Agente da Fase 4; trocar por `agente.integrado` quando existir."""
    from agente.agente_react import montar_investigador
    from agente.config import escolher_llm
    from agente.ferramentas import montar_ferramentas
    from agente.loja import FonteLoja
    from agente.memoria import MemoriaLongoPrazo, embeddings_padrao
    from agente.moderacao import moderar
    from agente.pipeline import montar_pipeline
    from agente.recuperacao import carregar_indice

    llm, emb = escolher_llm("openai"), embeddings_padrao()
    indice = carregar_indice(Path("dados/indice_faiss"), emb)

    def alvo(inputs: dict):
        memoria = MemoriaLongoPrazo(emb, Path(tempfile.mkdtemp()) / "m.json")
        fonte = FonteLoja.gravada(inputs["cenario"])
        ferramentas = montar_ferramentas(
            fonte, memoria=memoria, indice=indice, llm_acao=llm, estatisticas=True
        )
        investigador = montar_investigador(llm, ferramentas, max_passos=12)
        pipe = montar_pipeline(llm, moderar, investigacao=investigador, memoria=memoria)
        return pipe.invoke(
            {"mensagem": inputs["mensagem"], "historico": [], "session_id": "avaliacao"}
        )

    return alvo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enviar", action="store_true", help="envia ao LangSmith (ação externa)")
    parser.add_argument("--prefixo", default="fase5")
    args = parser.parse_args()
    load_dotenv()
    alvo = montar_alvo()
    if args.enviar:
        print(enviar_ao_langsmith(alvo, prefixo=args.prefixo))
        return
    linhas = avaliar_localmente(alvo, exemplos_dataset())
    for linha in linhas:
        print(linha["inputs"]["cenario"], linha["scores"], linha["erro"] or "")
    print("Médias:", resumo_metricas(linhas))


if __name__ == "__main__":
    main()
