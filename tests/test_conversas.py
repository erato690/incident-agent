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
    AnaliseIncidente,
    AnaliseNLU,
    Hipotese,
    RespostaFixa,
    RespostaTurno,
    ResultadoModeracao,
)

CONVERSAS = json.loads(
    (Path(__file__).parent.parent / "dados_dummy" / "fase1_conversas.json").read_text("utf-8")
)
ANALISE = AnaliseIncidente(
    severidade="alta",
    categoria="pool",
    servico="pedidos-api",
    resumo="Pool esgotado",
    hipoteses=[
        Hipotese(causa="pool esgotado", confianca=0.8, evidencia="HikariPool"),
        Hipotese(causa="deploy", confianca=0.4, evidencia="v3.2.0"),
    ],
    proximos_passos=["ver deploy"],
)
MOD_OK = ResultadoModeracao(status="ok")


class Espioes:
    """NLU e investigação falsos; guardam o que receberam (já mascarado)."""

    def __init__(self, conversa):
        self.intencoes = {
            mascarar(turno["mensagem"]): turno["intencao_esperada"] for turno in conversa["turnos"]
        }
        self.nlu_hist, self.inv_hist = [], []

    def nlu(self):
        def nlu_falso(estado):
            self.nlu_hist.append(list(estado["historico"]))
            return AnaliseNLU(intencao=self.intencoes[estado["mensagem"]], servico="pedidos-api")

        return RunnableLambda(nlu_falso)

    def investigacao(self):
        def nlu_falso(estado):
            self.inv_hist.append(list(estado["historico"]))
            return ANALISE

        return RunnableLambda(nlu_falso)


def _rodar(conversa):
    espioes = Espioes(conversa)
    pipeline = montar_pipeline(
        None, lambda turno: MOD_OK, nlu=espioes.nlu(), investigacao=espioes.investigacao()
    )
    return espioes, rodar_conversa(pipeline, conversa)


@pytest.mark.parametrize("conversa", CONVERSAS, ids=lambda conversa: conversa["id"])
def test_rotas_batem_com_o_esperado(conversa):
    _, respostas = _rodar(conversa)
    assert [resposta.rota for resposta in respostas] == [
        turno["rota_esperada"] for turno in conversa["turnos"]
    ]
    assert [resposta.nlu.intencao for resposta in respostas] == [
        turno["intencao_esperada"] for turno in conversa["turnos"]
    ]


@pytest.mark.parametrize("conversa", CONVERSAS, ids=lambda conversa: conversa["id"])
def test_historico_cresce_dois_por_turno_e_chega_ao_nlu(conversa):
    espioes, _ = _rodar(conversa)
    assert [len(historico) for historico in espioes.nlu_hist] == [
        2 * indice for indice in range(len(conversa["turnos"]))
    ]
    ultimo = espioes.nlu_hist[-1]
    assert isinstance(ultimo[0], HumanMessage) and isinstance(ultimo[1], AIMessage)


def test_historico_chega_mascarado_ao_nlu_e_a_investigacao():
    conversa = next(conversa for conversa in CONVERSAS if conversa["id"] == "escopo_externo")
    espioes, _ = _rodar(conversa)
    assert "senha=abc12345" in conversa["turnos"][1]["mensagem"]
    for hist in (*espioes.nlu_hist, *espioes.inv_hist):
        for mensagem in hist:
            assert "abc12345" not in mensagem.content
    assert any("senha=[SEGREDO]" in mensagem.content for mensagem in espioes.nlu_hist[-1])
    assert any("senha=[SEGREDO]" in mensagem.content for mensagem in espioes.inv_hist[-1])


@pytest.mark.parametrize("conversa", CONVERSAS, ids=lambda conversa: conversa["id"])
def test_turnos_fixos_nao_chamam_investigacao(conversa):
    espioes, _ = _rodar(conversa)
    investigados = sum(turno["rota_esperada"] == "investigacao" for turno in conversa["turnos"])
    assert len(espioes.inv_hist) == investigados < len(conversa["turnos"])


def test_json_tem_campos_obrigatorios():
    assert len(CONVERSAS) == 2
    for conversa in CONVERSAS:
        assert {"id", "titulo", "por_que", "turnos"} <= conversa.keys() and 5 <= len(
            conversa["turnos"]
        ) <= 6
        for turno in conversa["turnos"]:
            assert {
                "mensagem",
                "rota_esperada",
                "intencao_esperada",
                "hipoteses_devem_considerar",
            } <= turno.keys()
            if turno["rota_esperada"] == "investigacao":
                assert turno["hipoteses_devem_considerar"]
            else:
                assert turno["hipoteses_devem_considerar"] == []


def test_texto_resposta_fixa_investigacao_e_erro():
    fixa = RespostaTurno(
        rota="fixa",
        moderacao=MOD_OK,
        fixa=RespostaFixa(texto="Só investigo.", camada=2, categoria="fora_do_escopo"),
    )
    assert texto_resposta(fixa) == "Só investigo."
    texto_investigacao = texto_resposta(
        RespostaTurno(rota="investigacao", moderacao=MOD_OK, analise=ANALISE)
    )
    assert texto_investigacao.splitlines()[0] == "Pool esgotado"
    assert (
        "pool esgotado" in texto_investigacao
        and "deploy" in texto_investigacao
        and len(texto_investigacao.splitlines()) == 3
    )
    erro = RespostaTurno(rota="erro", moderacao=MOD_OK, erro="JSON inválido")
    assert texto_resposta(erro) == "JSON inválido"


def test_detalhe_mostra_deve_considerar_so_na_investigacao():
    from agente.bateria import detalhe_html

    mensagem = {
        "id": "c · turno 1",
        "mensagem": "x",
        "rota_esperada": "investigacao",
        "hipoteses_devem_considerar": ["causa externa"],
    }
    resposta = RespostaTurno(rota="investigacao", moderacao=MOD_OK, analise=ANALISE)
    assert "Deve considerar:</b> causa externa" in detalhe_html(mensagem, resposta)
    assert "Deve considerar" not in detalhe_html(
        {**mensagem, "hipoteses_devem_considerar": []}, resposta
    )
