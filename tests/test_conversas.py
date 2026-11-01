"""Conversas multi-turno: rotas, histórico mascarado e texto_resposta (sem rede)."""
import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from agente.bateria import rodar_conversa, texto_resposta
from agente.mascara import mascarar
from agente.pipeline import montar_pipeline
from agente.schemas import (
    AnaliseIncidente, AnaliseNLU, Hipotese, RespostaFixa, RespostaTurno, ResultadoModeracao,
)

CONVERSAS = json.loads(
    (Path(__file__).parent.parent / "dados_dummy" / "fase1_conversas.json").read_text("utf-8"))
ANALISE = AnaliseIncidente(
    severidade="alta", categoria="pool", servico="pedidos-api", resumo="Pool esgotado",
    hipoteses=[Hipotese(causa="pool esgotado", confianca=0.8, evidencia="HikariPool"),
               Hipotese(causa="deploy", confianca=0.4, evidencia="v3.8.1")],
    proximos_passos=["ver deploy"],
)
MOD_OK = ResultadoModeracao(status="ok")


class Espioes:
    """NLU e investigação falsos; guardam o que receberam (já mascarado)."""

    def __init__(self, conversa):
        self.intencoes = {mascarar(t["mensagem"]): t["intencao_esperada"] for t in conversa["turnos"]}
        self.nlu_hist, self.inv_hist = [], []

    def nlu(self):
        def f(e):
            self.nlu_hist.append(list(e["historico"]))
            return AnaliseNLU(intencao=self.intencoes[e["mensagem"]], servico="pedidos-api")
        return RunnableLambda(f)

    def investigacao(self):
        def f(estado):
            self.inv_hist.append(list(estado["historico"]))
            return ANALISE
        return RunnableLambda(f)


def _rodar(conversa):
    esp = Espioes(conversa)
    pipe = montar_pipeline(None, lambda t: MOD_OK, nlu=esp.nlu(), investigacao=esp.investigacao())
    return esp, rodar_conversa(pipe, conversa)


@pytest.mark.parametrize("conversa", CONVERSAS, ids=lambda c: c["id"])
def test_rotas_batem_com_o_esperado(conversa):
    _, rs = _rodar(conversa)
    assert [r.rota for r in rs] == [t["rota_esperada"] for t in conversa["turnos"]]
    assert [r.nlu.intencao for r in rs] == [t["intencao_esperada"] for t in conversa["turnos"]]


@pytest.mark.parametrize("conversa", CONVERSAS, ids=lambda c: c["id"])
def test_historico_cresce_dois_por_turno_e_chega_ao_nlu(conversa):
    esp, _ = _rodar(conversa)
    assert [len(h) for h in esp.nlu_hist] == [2 * i for i in range(len(conversa["turnos"]))]
    ultimo = esp.nlu_hist[-1]
    assert isinstance(ultimo[0], HumanMessage) and isinstance(ultimo[1], AIMessage)


def test_historico_chega_mascarado_ao_nlu_e_a_investigacao():
    conversa = next(c for c in CONVERSAS if c["id"] == "escopo_externo")
    esp, _ = _rodar(conversa)
    assert "senha=abc12345" in conversa["turnos"][1]["mensagem"]
    for hist in (*esp.nlu_hist, *esp.inv_hist):
        for m in hist:
            assert "abc12345" not in m.content
    assert any("senha=[SEGREDO]" in m.content for m in esp.nlu_hist[-1])
    assert any("senha=[SEGREDO]" in m.content for m in esp.inv_hist[-1])


@pytest.mark.parametrize("conversa", CONVERSAS, ids=lambda c: c["id"])
def test_turnos_fixos_nao_chamam_investigacao(conversa):
    esp, _ = _rodar(conversa)
    investigados = sum(t["rota_esperada"] == "investigacao" for t in conversa["turnos"])
    assert len(esp.inv_hist) == investigados < len(conversa["turnos"])


def test_json_tem_campos_obrigatorios():
    assert len(CONVERSAS) == 2
    for c in CONVERSAS:
        assert {"id", "titulo", "por_que", "turnos"} <= c.keys() and 5 <= len(c["turnos"]) <= 6
        for t in c["turnos"]:
            assert {"mensagem", "rota_esperada", "intencao_esperada",
                    "hipoteses_devem_considerar"} <= t.keys()
            if t["rota_esperada"] == "investigacao":
                assert t["hipoteses_devem_considerar"]
            else:
                assert t["hipoteses_devem_considerar"] == []


def test_texto_resposta_fixa_investigacao_e_erro():
    fixa = RespostaTurno(rota="fixa", moderacao=MOD_OK,
                         fixa=RespostaFixa(texto="Só investigo.", camada=2, categoria="fora_do_escopo"))
    assert texto_resposta(fixa) == "Só investigo."
    inv = texto_resposta(RespostaTurno(rota="investigacao", moderacao=MOD_OK, analise=ANALISE))
    assert inv.splitlines()[0] == "Pool esgotado"
    assert "pool esgotado" in inv and "deploy" in inv and len(inv.splitlines()) == 3
    erro = RespostaTurno(rota="erro", moderacao=MOD_OK, erro="JSON inválido")
    assert texto_resposta(erro) == "JSON inválido"


def test_detalhe_mostra_deve_considerar_so_na_investigacao():
    from agente.bateria import detalhe_html
    m = {"id": "c · turno 1", "mensagem": "x", "rota_esperada": "investigacao",
         "hipoteses_devem_considerar": ["causa externa"]}
    r = RespostaTurno(rota="investigacao", moderacao=MOD_OK, analise=ANALISE)
    assert "Deve considerar:</b> causa externa" in detalhe_html(m, r)
    assert "Deve considerar" not in detalhe_html({**m, "hipoteses_devem_considerar": []}, r)
