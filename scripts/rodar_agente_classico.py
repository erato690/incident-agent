"""Roda os 2 turnos da seção 2.7 do projeto.ipynb (agente clássico com memória).

Uso: .venv/bin/python scripts/rodar_agente_classico.py [openai|deepseek]
Precisa da chave do provedor no .env; usa `LOJA_URL` se definida, senão o cenário gravado.
"""

import sys
import warnings
from pathlib import Path

from langchain_core._api import LangChainDeprecationWarning

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agente.classico import ferramentas_uma_entrada, montar_agente_classico  # noqa: E402
from agente.config import escolher_llm  # noqa: E402
from agente.loja import fonte_padrao  # noqa: E402

CENARIO = "deploy_com_bug"
PERGUNTA_1 = "O pagamentos-api devolve 500 desde as 14h38. Existe algum deploy perto desse horário?"
PERGUNTA_2 = "E o que mudou nesse deploy? Compare com a versão anterior."


def main(provedor: str | None = None) -> None:
    llm = escolher_llm(provedor)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)
        classico = montar_agente_classico(llm, ferramentas_uma_entrada(fonte_padrao(CENARIO)))
        primeira = classico.invoke({"input": PERGUNTA_1})
        print("\nRESPOSTA 1:", primeira["output"], "\n")
        segunda = classico.invoke({"input": PERGUNTA_2})
        print("\nRESPOSTA 2:", segunda["output"])
        print("\nMemória de buffer:\n", classico.memory.buffer)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
