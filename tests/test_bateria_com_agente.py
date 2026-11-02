"""Bateria da Fase 2: cenário por mensagem/conversa, coluna de ferramentas, sem modelo real."""

import json
from pathlib import Path

from langchain_core.runnables import RunnableLambda

from agente.agente_react import montar_investigacao_agente
from agente.bateria import (
    detalhe_html,
    linhas_bateria,
    nomes_ferramentas,
    rodar_bateria,
    rodar_conversa,
)
from agente.ferramentas import montar_ferramentas
from agente.loja import FonteLoja
from agente.pipeline import montar_pipeline
from agente.schemas import AnaliseNLU, PassoTrajetoria, RespostaTurno, ResultadoModeracao
from tests.fakes import chamada, roteiro
from tests.test_agente_react import JSON_OK

DADOS = Path(__file__).parent.parent / "dados_dummy"
RAIZ = Path(__file__).parent / "dados"
MENSAGENS = json.loads((DADOS / "fase2_mensagens.json").read_text(encoding="utf-8"))
CONVERSAS = json.loads((DADOS / "fase2_conversas.json").read_text(encoding="utf-8"))
NLU_POR_ROTA = {"investigacao": "investigar_erro"}


def _nlu_pela_esperada(esperadas: dict):
    """NLU falso: devolve a intenção esperada da mensagem (a NLU real é testada na Fase 1)."""
    return RunnableLambda(lambda estado: AnaliseNLU(intencao=esperadas[estado["mensagem"]]))


def _moderar(texto):
    return ResultadoModeracao(status="ok")


def _fabrica(modelos: dict, cenarios_pedidos: list, esperadas: dict):
    def fabrica(cenario: str):
        cenarios_pedidos.append(cenario)
        fonte = FonteLoja.gravada("cenario_teste", raiz=RAIZ)
        modelo = roteiro(chamada("buscar_logs", {"servico": "pagamentos-api"}), JSON_OK)
        modelos[cenario] = modelo
        investigacao = montar_investigacao_agente(modelo, montar_ferramentas(fonte))
        return montar_pipeline(
            None, _moderar, nlu=_nlu_pela_esperada(esperadas), investigacao=investigacao
        )

    return fabrica


def test_dados_fase2_bem_formados():
    assert len(MENSAGENS) >= 12
    assert (
        len({mensagem["cenario"] for mensagem in MENSAGENS if mensagem["grupo"] == "investigacao"})
        == 8
    )
    for mensagem in MENSAGENS:
        assert {
            "cenario",
            "causa_esperada",
            "ferramentas_esperadas",
            "rota_esperada",
        } <= mensagem.keys()
        assert mensagem["cenario"] not in mensagem["mensagem"]
    assert [conversa["id"] for conversa in CONVERSAS] == ["deploy_investigado", "deploy_distrator"]
    assert all(4 <= len(conversa["turnos"]) <= 5 for conversa in CONVERSAS)


def test_bateria_com_fabrica_rotas_batem_e_cenario_nunca_vai_ao_modelo():
    esperadas = {mensagem["mensagem"]: mensagem["intencao_esperada"] for mensagem in MENSAGENS}
    pedidos, modelos = [], {}
    respostas = rodar_bateria(_fabrica(modelos, pedidos, esperadas), MENSAGENS)
    assert [resposta.rota for resposta in respostas] == [
        mensagem["rota_esperada"] for mensagem in MENSAGENS
    ]
    assert pedidos == list(
        dict.fromkeys(mensagem["cenario"] for mensagem in MENSAGENS)
    )  # uma vez por cenário
    enviado = " ".join(
        str(msg.content)
        for modelo in modelos.values()
        for chamada in modelo.chamadas
        for msg in chamada
    )
    assert all(mensagem["causa_esperada"] not in enviado for mensagem in MENSAGENS)
    assert all(mensagem["cenario"] not in enviado for mensagem in MENSAGENS)


def test_bateria_com_pipeline_fixo_continua_funcionando():
    pipeline = montar_pipeline(
        None,
        _moderar,
        nlu=RunnableLambda(lambda estado: AnaliseNLU(intencao="saudacao")),
        investigacao=RunnableLambda(lambda estado: "nunca chamada"),
    )
    respostas = rodar_bateria(pipeline, [{"id": "a", "mensagem": "oi", "rota_esperada": "fixa"}])
    assert respostas[0].rota == "fixa"


def test_coluna_ferramentas_na_tabela_e_no_detalhe():
    passos = [
        PassoTrajetoria(
            ferramenta=nome,
            argumentos={"servico": "x"},
            duracao_ms=12,
            tamanho=5,
            reserva=(nome == "comparar_versoes"),
        )
        for nome in ["buscar_logs", "buscar_logs", "comparar_versoes", "buscar_logs"]
    ]
    resposta = RespostaTurno(
        rota="erro", erro="x", moderacao=ResultadoModeracao(status="ok"), trajetoria=passos
    )
    mensagem = {
        "id": "a",
        "grupo": "investigacao",
        "mensagem": "m",
        "rota_esperada": "erro",
        "causa_esperada": "CAUSA-GABARITO",
    }
    assert nomes_ferramentas(resposta) == ["buscar_logs", "comparar_versoes", "buscar_logs"]
    linha = linhas_bateria([mensagem], [resposta])[0]
    assert linha["ferramentas"] == "buscar_logs → comparar_versoes → buscar_logs"
    html = detalhe_html(mensagem, resposta)
    assert "12 ms" in html and "reserva" in html and "comparar_versoes" in html
    assert "CAUSA-GABARITO" in html and "informativo" in html.lower()


def test_sem_trajetoria_a_coluna_some_como_na_fase1():
    resposta = RespostaTurno(rota="fixa", moderacao=ResultadoModeracao(status="ok"))
    assert (
        "ferramentas"
        not in linhas_bateria([{"id": "a", "mensagem": "m", "rota_esperada": "fixa"}], [resposta])[
            0
        ]
    )


def test_conversa_com_fabrica_usa_o_cenario_da_conversa():
    conversa = {**CONVERSAS[0], "turnos": CONVERSAS[0]["turnos"][:2]}
    esperadas = {turno["mensagem"]: turno["intencao_esperada"] for turno in conversa["turnos"]}
    pedidos, modelos = [], {}
    respostas = rodar_conversa(_fabrica(modelos, pedidos, esperadas), conversa)
    assert pedidos == [conversa["cenario"]] and len(respostas) == 2
    enviado = " ".join(
        str(msg.content) for chamada in modelos[conversa["cenario"]].chamadas for msg in chamada
    )
    assert conversa["cenario"] not in enviado
