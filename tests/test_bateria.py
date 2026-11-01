"""Relatório da bateria: linhas da tabela e detalhe HTML (sem LLM, sem rede)."""
from agente.bateria import GRUPOS, detalhe_html, linhas_bateria
from agente.schemas import (
    AnaliseIncidente, AnaliseNLU, Hipotese, RespostaFixa, RespostaTurno, ResultadoModeracao,
)

ANALISE = AnaliseIncidente(
    severidade="alta", categoria="npe", servico="pagamentos-api", resumo="NPE após deploy",
    hipoteses=[Hipotese(causa="cupom nulo", confianca=0.8, evidencia="cupom is null"),
               Hipotese(causa="pool", confianca=0.2, evidencia_insuficiente=True,
                        dado_que_falta="métrica do pool")],
    proximos_passos=["ver diff"])

INV = RespostaTurno(rota="investigacao", moderacao=ResultadoModeracao(status="aviso",
                    categorias=["violence"], scores={"violence": 0.6}),
                    nlu=AnaliseNLU(intencao="investigar_erro"), analise=ANALISE)
FIXA = RespostaTurno(rota="fixa", moderacao=ResultadoModeracao(status="ok"),
                     nlu=AnaliseNLU(intencao="saudacao"),
                     fixa=RespostaFixa(texto="Olá! <oi>", camada=2, categoria="saudacao"))
MSGS = [
    {"id": "a", "grupo": "investigacao", "mensagem": "erro senha=Sup3r", "rota_esperada": "investigacao"},
    {"id": "b", "grupo": "barreira", "mensagem": "bom dia", "rota_esperada": "investigacao"},
]


def test_linhas_com_colunas_e_ok():
    linhas = linhas_bateria(MSGS, [INV, FIXA])
    assert list(linhas[0]) == ["id", "grupo", "esperada", "obtida", "intenção", "moderação", "ok"]
    assert linhas[0]["ok"] is True and linhas[1]["ok"] is False
    assert linhas[0]["moderação"] == "aviso (violence)"
    assert linhas[1]["grupo"] == GRUPOS["barreira"]


def test_detalhe_investigacao_mostra_hipoteses_e_mascara():
    h = detalhe_html(MSGS[0], INV)
    assert h.startswith("<details>") and "a — ok" in h
    assert "Sup3r" not in h and "[SEGREDO]" in h
    assert "cupom nulo" in h and "0.80" in h and "insuficiente" in h and "alta" in h
    assert "métrica do pool" in h


def test_detalhe_fixa_mostra_texto_camada_e_escapa_html():
    h = detalhe_html(MSGS[1], FIXA)
    assert "b — FALHOU" in h and "camada 2" in h and "&lt;oi&gt;" in h
