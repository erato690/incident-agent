"""Rastreamento do LangSmith: desligado por padrão, ligado só no bloco que pede.

O projeto inteiro (app, baterias, conversa longa, avaliação local) roda com
`LANGSMITH_TRACING=false`. A seção 5 do notebook liga o rastreamento só onde precisa, com
`langsmith.tracing_context(enabled=True)`: o envio do dataset e do experimento e uma execução do
agente integrado por cenário. Falha do LangSmith (429, cota, autenticação, rede) vira aviso,
nunca exceção: a célula mostra o aviso e o notebook segue.
"""

import logging
import os
from collections.abc import Callable, Iterable
from typing import Any

from langsmith import tracing_context

LOGGERS_LANGSMITH = ("langsmith", "langchain_core.tracers")


def desligar_rastreamento_por_padrao() -> None:
    """Sem `LANGSMITH_TRACING` no ambiente (nem no `.env`), o rastreamento fica desligado."""
    os.environ.setdefault("LANGSMITH_TRACING", "false")


class _Coletor(logging.Handler):
    """Guarda os avisos que o envio em segundo plano registra no log (ex.: 429 no ingest)."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.mensagens: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.mensagens.append(record.getMessage())


def _esperar_envio() -> None:
    """Espera os traces pendentes saírem (o envio roda em outra thread)."""
    from langchain_core.tracers.langchain import wait_for_all_tracers

    wait_for_all_tracers()


def _curto(texto: str, limite: int = 200) -> str:
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= limite else texto[: limite - 3] + "..."


def _aviso(motivo: str) -> str:
    return f"LangSmith indisponível, a célula seguiu sem o envio: {_curto(motivo)}"


def com_rastreamento(funcao: Callable[[], Any], esperar: bool = True) -> tuple[Any, str | None]:
    """Roda `funcao()` com o rastreamento ligado só neste bloco; devolve (resultado, aviso).

    Qualquer exceção vira aviso (resultado None). Avisos do envio em segundo plano também.
    """
    coletor = _Coletor()
    loggers = [logging.getLogger(nome) for nome in LOGGERS_LANGSMITH]
    propagacao = [logger.propagate for logger in loggers]
    for logger in loggers:
        logger.addHandler(coletor)
        logger.propagate = False
    resultado, aviso = None, None
    try:
        with tracing_context(enabled=True):
            resultado = funcao()
        if esperar:
            _esperar_envio()
    except Exception as erro:  # noqa: BLE001 - o notebook não pode cair por causa do LangSmith
        aviso = _aviso(f"{type(erro).__name__}: {erro}")
    finally:
        for logger, propaga in zip(loggers, propagacao, strict=True):
            logger.removeHandler(coletor)
            logger.propagate = propaga
    if aviso is None and coletor.mensagens:
        aviso = _aviso(coletor.mensagens[0])
    return resultado, aviso


def apresentar_cenarios(
    rodar: Callable[[str], Any], cenarios: Iterable[str], esperar: bool = True
) -> tuple[list[dict], str | None]:
    """Uma execução rastreada por cenário, numa única apresentação.

    Falha de um cenário fica na linha dele (`erro`) e não interrompe os outros; o aviso é só
    do LangSmith.
    """

    def todas() -> list[dict]:
        linhas = []
        for cenario in cenarios:
            try:
                linhas.append({"cenario": cenario, "resultado": rodar(cenario), "erro": None})
            except Exception as erro:  # noqa: BLE001 - o próximo cenário roda mesmo assim
                falha = f"{type(erro).__name__}: {erro}"
                linhas.append({"cenario": cenario, "resultado": None, "erro": falha})
        return linhas

    linhas, aviso = com_rastreamento(todas, esperar=esperar)
    return linhas or [], aviso
