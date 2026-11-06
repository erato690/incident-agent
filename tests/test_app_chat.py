"""Funções puras de apoio à API do chat (sem chave)."""

from agente.schemas import (
    AnaliseIncidente,
    AnaliseNLU,
    Hipotese,
    PassoTrajetoria,
    RespostaTurno,
)
from app.formatacao import (
    dados_faltantes,
    fontes_consultadas,
    mensagem_erro,
    rotulo_ferramenta,
)


def _resposta(**campos) -> RespostaTurno:
    return RespostaTurno.model_validate(
        {"rota": "investigacao", "moderacao": {"status": "ok"}, **campos}
    )


def _analise(falta: str | None = None) -> AnaliseIncidente:
    return AnaliseIncidente(
        severidade="critica",
        categoria="banco",
        resumo="r",
        hipoteses=[
            Hipotese(causa="a", confianca=0.8, evidencia="e"),
            Hipotese(
                causa="b",
                confianca=0.2,
                evidencia=None if falta else "e2",
                evidencia_insuficiente=falta is not None,
                dado_que_falta=falta,
            ),
        ],
        proximos_passos=["p"],
    )


def test_dados_faltantes_so_do_nlu_e_da_principal():
    nlu = AnaliseNLU.model_construct(dado_faltante="Métricas do pool")
    resposta = _resposta(analise=_analise("métricas do pool"))
    resposta.nlu = nlu
    # o dado da hipótese secundária não vira pergunta; o do NLU sim
    assert dados_faltantes(resposta) == ["Métricas do pool"]
    assert dados_faltantes(_resposta(analise=_analise("métricas do pool"))) == []


def test_fontes_e_passos():
    passos = [
        PassoTrajetoria(ferramenta="buscar_logs", duracao_ms=5, tamanho=1),
        PassoTrajetoria(ferramenta="buscar_logs", duracao_ms=6, tamanho=1, reserva=True),
        PassoTrajetoria(ferramenta="x", duracao_ms=1, tamanho=1, erro="falhou"),
    ]
    assert fontes_consultadas(_resposta(trajetoria=passos)) == ["logs da loja", "x"]
    assert rotulo_ferramenta("consultar_sql") == "histórico de incidentes (SQL)"


def test_mensagem_erro_so_primeira_linha():
    texto = mensagem_erro(RuntimeError("timeout\nlinha 2"))
    assert "RuntimeError: timeout" in texto and "linha 2" not in texto
