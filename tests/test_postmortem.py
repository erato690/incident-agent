from datetime import datetime

from agente.postmortem import (
    DadosPostMortem,
    ItemLinhaDoTempo,
    gerar_postmortem,
    linha_do_tempo_da_trajetoria,
    salvar_postmortem,
)
from agente.schemas import (
    AcaoSugerida,
    AnaliseIncidente,
    Episodio,
    Hipotese,
    PassoTrajetoria,
)

AGORA = datetime(2026, 11, 5, 10, 30)


def _analise(resumo: str = "Pool de conexões esgotado") -> AnaliseIncidente:
    return AnaliseIncidente(
        severidade="alta",
        categoria="banco",
        resumo=resumo,
        hipoteses=[
            Hipotese(causa="Pool esgotado", confianca=0.8, evidencia="timeout"),
            Hipotese(causa="Deploy ruim", confianca=0.3, evidencia="v2"),
        ],
        proximos_passos=["Adicionar alerta de pool"],
        acoes_sugeridas=[
            AcaoSugerida(acao="Reiniciar o pool", motivo="libera conexões", risco="baixo")
        ],
    )


def _episodio() -> Episodio:
    return Episodio(
        incidente_id="INC-1",
        session_id="s",
        servico="shop",
        resumo="Pool pequeno demais",
        causa="Pool de 5 conexões",
        evidencia="log 10:15",
        origem="engenheiro",
        criado_em=AGORA,
    )


def _dados(**kw) -> DadosPostMortem:
    base = {"incidente_id": "INC-1", "servico": "shop", "gerado_em": AGORA, "analise": _analise()}
    return DadosPostMortem(**{**base, **kw})


def test_com_causa_confirmada():
    texto = gerar_postmortem(_dados(episodio=_episodio()))
    assert "causa não confirmada" not in texto
    assert "Causa confirmada: Pool de 5 conexões" in texto
    for secao in (
        "Resumo",
        "Impacto e severidade",
        "Linha do tempo",
        "Causa raiz e evidências",
        "Ações preventivas",
        "Lições aprendidas",
    ):
        assert f"## {secao}" in texto


def test_sem_causa_confirmada():
    texto = gerar_postmortem(_dados())
    assert "(causa não confirmada)" in texto.splitlines()[0]
    assert "Causa não confirmada pelo engenheiro; hipóteses: Pool esgotado" in texto


def test_acoes_nao_executadas():
    texto = gerar_postmortem(_dados())
    assert "Reiniciar o pool" in texto
    assert "sugerida (não executada)" in texto


def test_mascara_segredo():
    texto = gerar_postmortem(_dados(analise=_analise("falha com password=abc123xyz no log")))
    assert "abc123xyz" not in texto
    assert "[SEGREDO]" in texto


def test_salvar(tmp_path):
    caminho = salvar_postmortem(_dados(), tmp_path / "novo" / "pm")
    assert caminho.name == "postmortem_INC-1.md"
    assert caminho.read_text(encoding="utf-8").startswith("# Post-mortem INC-1")


def test_linha_do_tempo_da_trajetoria():
    passos = [
        PassoTrajetoria(
            ferramenta="logs", argumentos={"servico": "shop"}, duracao_ms=5, tamanho=10
        ),
        PassoTrajetoria(ferramenta="metricas", argumentos={}, duracao_ms=5, tamanho=10),
    ]
    itens = linha_do_tempo_da_trajetoria(passos)
    assert len(itens) == 2
    assert "logs(servico=shop)" in itens[0].evento


def test_linha_do_tempo_com_observacao():
    passo = PassoTrajetoria(ferramenta="logs", duracao_ms=1, tamanho=1)
    object.__setattr__(passo, "observacao", "10:15 erro de timeout\nsem hora")
    itens = linha_do_tempo_da_trajetoria([passo])
    assert [i.horario for i in itens] == ["10:15", None]
    assert isinstance(itens[0], ItemLinhaDoTempo)
