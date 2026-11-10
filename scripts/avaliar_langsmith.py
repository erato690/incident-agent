"""Avalia o agente integrado nos cenários: local por padrão; `--enviar` publica no LangSmith.

Uso: .venv/bin/python scripts/avaliar_langsmith.py [--enviar] [--prefixo fase5]

O rastreamento fica desligado (LANGSMITH_TRACING=false) na avaliação local. Com `--enviar`, só o
envio (dataset + experimento) roda com o rastreamento ligado; falha do LangSmith (429, cota,
rede) vira aviso e o script termina sem erro.
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
    saida_do_turno,
)
from agente.rastreamento import com_rastreamento, desligar_rastreamento_por_padrao  # noqa: E402


def montar_alvo() -> Callable[[dict], dict]:
    """Um agente integrado novo por exemplo (memória própria), uma sessão no cenário."""
    from agente.config import escolher_llm
    from agente.integrado import montar_agente_integrado

    llm = escolher_llm("openai")
    base = montar_agente_integrado(llm)
    pasta = Path(tempfile.mkdtemp(prefix="postmortem_"))

    def alvo(inputs: dict) -> dict:
        agente = montar_agente_integrado(
            llm, embeddings=base.embeddings, indice=base.indice, pasta_postmortem=pasta
        )
        sessao = agente.abrir_sessao(inputs["cenario"])
        return saida_do_turno(agente.turno(sessao, inputs["mensagem"]))

    return alvo


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enviar", action="store_true", help="envia ao LangSmith (ação externa)")
    parser.add_argument("--prefixo", default="fase5")
    args = parser.parse_args(argv)
    load_dotenv()
    desligar_rastreamento_por_padrao()
    alvo = montar_alvo()
    if args.enviar:
        experimento, aviso = com_rastreamento(
            lambda: enviar_ao_langsmith(alvo, prefixo=args.prefixo)
        )
        print(
            aviso or f"Experimento enviado: {getattr(experimento, 'experiment_name', experimento)}"
        )
        return
    linhas = avaliar_localmente(alvo, exemplos_dataset())
    for linha in linhas:
        print(linha["inputs"]["cenario"], linha["scores"], linha["erro"] or "")
    print("Médias:", resumo_metricas(linhas))


if __name__ == "__main__":
    main()
