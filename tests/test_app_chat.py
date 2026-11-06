"""Funções puras de apoio à tela de chat (sem Streamlit nem chave)."""

from agente.schemas import (
    AnaliseIncidente,
    AnaliseNLU,
    Auditoria,
    Hipotese,
    PassoTrajetoria,
    RespostaTurno,
)
from app.formatacao import (
    dados_faltantes,
    fontes_consultadas,
    linhas_passos,
    mensagem_erro,
    selo,
    selo_auditor,
    selo_risco,
    selo_severidade,
    sugestoes_iniciais,
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


def test_selos_dizem_o_nivel_em_texto():
    assert selo_severidade("critica") == ":red-badge[Severidade crítica]"
    assert selo_risco("medio") == ":orange-badge[Risco médio]"
    assert selo("x [y]", "gray") == ":gray-badge[x (y)]"


def test_selo_auditor():
    assert "Não auditada" in selo_auditor(_resposta())
    assert "aprovou" in selo_auditor(_resposta(auditoria=Auditoria(aprovada=True)))
    assert "reprovou" in selo_auditor(_resposta(auditoria=Auditoria(aprovada=False)))


def test_dados_faltantes_sem_repeticao():
    nlu = AnaliseNLU.model_construct(dado_faltante="Métricas do pool")
    resposta = _resposta(analise=_analise("métricas do pool"))
    resposta.nlu = nlu
    assert dados_faltantes(resposta) == ["métricas do pool"]
    assert dados_faltantes(_resposta(analise=_analise())) == []


def test_fontes_e_passos():
    passos = [
        PassoTrajetoria(ferramenta="buscar_logs", duracao_ms=5, tamanho=1),
        PassoTrajetoria(ferramenta="buscar_logs", duracao_ms=6, tamanho=1, reserva=True),
        PassoTrajetoria(ferramenta="x", duracao_ms=1, tamanho=1, erro="falhou"),
    ]
    assert fontes_consultadas(_resposta(trajetoria=passos)) == ["logs da loja", "x"]
    linhas = linhas_passos(passos)
    assert linhas[0] == "1. Consultou logs da loja (`buscar_logs`, 5 ms)"
    assert linhas[1].endswith("usou dados gravados") and linhas[2].endswith("falhou")


def test_sugestoes_e_erro():
    assert all("pedidos-api" in s for s in sugestoes_iniciais("pedidos-api")[:2])
    assert "o serviço" in sugestoes_iniciais(None)[0]
    texto = mensagem_erro(RuntimeError("timeout\nlinha 2"))
    assert "RuntimeError: timeout" in texto and "linha 2" not in texto
