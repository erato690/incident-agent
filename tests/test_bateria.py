"""Relatório da bateria: linhas da tabela e detalhe HTML (sem LLM, sem rede)."""

from datetime import datetime

from agente.bateria import GRUPOS, detalhe_html, linhas_bateria
from agente.schemas import (
    AnaliseIncidente,
    AnaliseNLU,
    Hipotese,
    RespostaFixa,
    RespostaTurno,
    ResultadoModeracao,
)

ANALISE = AnaliseIncidente(
    severidade="alta",
    categoria="npe",
    servico="pagamentos-api",
    resumo="NPE após deploy",
    hipoteses=[
        Hipotese(causa="cupom nulo", confianca=0.8, evidencia="cupom is null"),
        Hipotese(
            causa="pool",
            confianca=0.2,
            evidencia_insuficiente=True,
            dado_que_falta="métrica do pool",
        ),
    ],
    proximos_passos=["ver diff"],
)

INV = RespostaTurno(
    rota="investigacao",
    moderacao=ResultadoModeracao(status="aviso", categorias=["violence"], scores={"violence": 0.6}),
    nlu=AnaliseNLU(intencao="investigar_erro"),
    analise=ANALISE,
)
FIXA = RespostaTurno(
    rota="fixa",
    moderacao=ResultadoModeracao(status="ok"),
    nlu=AnaliseNLU(intencao="saudacao"),
    fixa=RespostaFixa(texto="Olá! <oi>", camada=2, categoria="saudacao"),
)
MSGS = [
    {
        "id": "a",
        "grupo": "investigacao",
        "mensagem": "erro senha=Sup3r",
        "rota_esperada": "investigacao",
    },
    {"id": "b", "grupo": "barreira", "mensagem": "bom dia", "rota_esperada": "investigacao"},
]


def test_linhas_com_colunas_e_ok():
    linhas = linhas_bateria(MSGS, [INV, FIXA])
    assert list(linhas[0]) == ["id", "grupo", "esperada", "obtida", "intenção", "moderação", "ok"]
    assert linhas[0]["ok"] is True and linhas[1]["ok"] is False
    assert linhas[0]["moderação"] == "aviso (violence)"
    assert linhas[1]["grupo"] == GRUPOS["barreira"]


def test_detalhe_investigacao_mostra_hipoteses_e_mascara():
    html = detalhe_html(MSGS[0], INV)
    assert html.startswith("<details>") and "a — ok" in html
    assert "Sup3r" not in html and "[SEGREDO]" in html
    assert "cupom nulo" in html and "0.80" in html and "insuficiente" in html and "alta" in html
    assert "métrica do pool" in html


def test_detalhe_fixa_mostra_texto_camada_e_escapa_html():
    html = detalhe_html(MSGS[1], FIXA)
    assert "b — FALHOU" in html and "camada 2" in html and "&lt;oi&gt;" in html


# --- Fase 4: causa certa, fato registrado e ações sugeridas ----------------------------------

from agente.bateria import acertou, causa_certa, memoria_registrada  # noqa: E402
from agente.schemas import AcaoSugerida, FatoSemantico  # noqa: E402


def _analise(principal="Reindexação REINDEX bloqueia a tabela", acoes=None):
    return ANALISE.model_copy(
        update={
            "hipoteses": [
                Hipotese(
                    causa="deploy do e-mail",
                    confianca=0.1,
                    evidencia_insuficiente=True,
                    dado_que_falta="diff do deploy",
                ),
                Hipotese(causa=principal, confianca=0.8, evidencia="consultar_estatisticas_banco"),
            ],
            "acoes_sugeridas": acoes or [],
        }
    )


def _inv(analise):
    return INV.model_copy(update={"analise": analise})


def test_causa_certa_none_sem_palavras_causa():
    assert causa_certa({"id": "x"}, _inv(_analise())) is None


def test_causa_certa_usa_a_hipotese_de_maior_confianca_sem_caixa():
    mensagem = {"palavras_causa": ["reindex"]}
    assert causa_certa(mensagem, _inv(_analise())) is True
    assert causa_certa({"palavras_causa": ["deploy"]}, _inv(_analise())) is False
    assert causa_certa({"palavras_causa": ["x", "BLOQUEIA"]}, _inv(_analise())) is True


def test_causa_certa_false_sem_analise():
    assert causa_certa({"palavras_causa": ["pool"]}, FIXA) is False


def test_coluna_causa_certa_so_aparece_se_algum_item_tem_palavras():
    sem = linhas_bateria(MSGS, [INV, FIXA])
    assert "causa certa" not in sem[0]
    msgs = [{**MSGS[0], "palavras_causa": ["reindex"]}, {**MSGS[1], "palavras_causa": ["x"]}]
    linhas = linhas_bateria(msgs, [_inv(_analise()), FIXA])
    assert [linha["causa certa"] for linha in linhas] == ["sim", "não"]
    assert linhas[0]["ok"] is True  # acertou() continua só pela rota


def test_grava_fato_esperado_entra_no_acertou():
    fato = FatoSemantico(
        assunto="X", fato="y", fonte="usuario", verificado_em=datetime(2026, 11, 5)
    )
    gravou = RespostaTurno(rota="memoria", moderacao=ResultadoModeracao(status="ok"), fato=fato)
    mensagem = {"id": "f", "rota_esperada": "memoria", "grava_fato_esperado": True}
    assert acertou(mensagem, gravou) is True
    assert acertou(mensagem, gravou.model_copy(update={"fato": None})) is False
    nao = {**mensagem, "grava_fato_esperado": False}
    assert acertou(nao, gravou) is False
    assert memoria_registrada(gravou) == "fato registrado"


def test_detalhe_mostra_acoes_sugeridas_nao_executadas():
    acao = AcaoSugerida(acao="Aguardar <REINDEX>", motivo="bloqueio", risco="baixo")
    html = detalhe_html(MSGS[0], _inv(_analise(acoes=[acao])))
    assert "sugerida (não executada)" in html and "Aguardar &lt;REINDEX&gt;" in html
    assert "risco baixo" in html
    assert "Ações sugeridas" not in detalhe_html(MSGS[0], INV)
