"""TrajetoriaCallback grava as chamadas de ferramenta em ordem."""

import contextlib

from langchain_core.tools import tool

from agente.github import MARCA_RESERVA, PREFIXO_MOTIVO
from agente.trajetoria import LIMITE_OBSERVACAO, TrajetoriaCallback


@tool
def eco(texto: str) -> str:
    """Devolve o texto."""
    return f"ok {texto}"


@tool
def da_reserva(texto: str) -> str:
    """Resposta da reserva."""
    return f"{MARCA_RESERVA}\n{PREFIXO_MOTIVO}no network: X\ndados"


@tool
def quebra(texto: str) -> str:
    """Sempre falha."""
    raise ValueError("falhou de propósito")


def test_grava_ferramenta_argumentos_duracao_e_tamanho_em_ordem():
    callback = TrajetoriaCallback()
    eco.invoke({"texto": "a"}, config={"callbacks": [callback]})
    eco.invoke({"texto": "bb"}, config={"callbacks": [callback]})
    passos = callback.passos
    assert [passo.ferramenta for passo in passos] == ["eco", "eco"]
    assert passos[0].argumentos == {"texto": "a"} and passos[1].argumentos == {"texto": "bb"}
    assert passos[0].tamanho == len("ok a") and passos[0].duracao_ms >= 0
    assert passos[0].erro is None and passos[0].reserva is False


def test_reserva_detectada_na_observacao():
    callback = TrajetoriaCallback()
    da_reserva.invoke({"texto": "1"}, config={"callbacks": [callback]})
    assert callback.passos[0].reserva is True
    assert callback.passos[0].motivo_reserva == "no network: X"


def test_erro_da_ferramenta_fica_no_passo():
    callback = TrajetoriaCallback()
    with contextlib.suppress(ValueError):
        quebra.invoke({"texto": "1"}, config={"callbacks": [callback]})
    assert len(callback.passos) == 1 and "falhou de propósito" in callback.passos[0].erro


def test_observacao_guardada_e_truncada_no_limite():
    from agente.schemas import PassoTrajetoria

    callback = TrajetoriaCallback()
    eco.invoke({"texto": "a"}, config={"callbacks": [callback]})
    eco.invoke({"texto": "x" * 9000}, config={"callbacks": [callback]})
    assert callback.passos[0].observacao == "ok a"
    assert len(callback.passos[1].observacao) == LIMITE_OBSERVACAO
    assert callback.passos[1].tamanho == 9003  # tamanho continua o original
    assert PassoTrajetoria(ferramenta="f", duracao_ms=0, tamanho=0).observacao is None


def test_resposta_turno_tem_auditoria_e_aviso_opcionais():
    from agente.schemas import Auditoria, RespostaTurno, ResultadoModeracao

    base = {"rota": "fixa", "moderacao": ResultadoModeracao(status="ok")}
    assert RespostaTurno(**base).auditoria is None and RespostaTurno(**base).aviso is None
    resposta = RespostaTurno(**base, auditoria=Auditoria(aprovada=True), aviso="x")
    assert resposta.auditoria.aprovada and resposta.aviso == "x"
