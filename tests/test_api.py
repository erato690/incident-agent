"""API web (FastAPI) com agente falso: sessões, mensagens, passos por SSE, post-mortem e análise."""

import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool

from agente.conversa import abrir_sessao
from agente.registro import Registro, RegistroTurno
from agente.schemas import (
    AcaoSugerida,
    AnaliseIncidente,
    Auditoria,
    Hipotese,
    PassoTrajetoria,
    RespostaFixa,
    RespostaTurno,
)
from app.main import criar_app


@tool
def buscar_logs(servico: str) -> str:
    """Logs falsos."""
    return "ok"


def _analise() -> AnaliseIncidente:
    return AnaliseIncidente(
        severidade="alta",
        categoria="banco",
        resumo="Timeouts no pedidos-api.",
        hipoteses=[
            Hipotese(causa="Deploy v3.2.1", confianca=0.8, evidencia="deploy às 13:40"),
            Hipotese(
                causa="Pool",
                confianca=0.3,
                evidencia_insuficiente=True,
                dado_que_falta="métricas do pool",
            ),
        ],
        proximos_passos=["Verificar deploy"],
        acoes_sugeridas=[AcaoSugerida(acao="Reverter", motivo="Coincide.", risco="medio")],
    )


class AgenteFalso:
    """Mesma fachada do AgenteIntegrado; passa por runnables nomeados como o pipeline real."""

    def __init__(self):
        self.registro = Registro()
        self.mensagens: list[str] = []

    def abrir_sessao(self, cenario, incidente_id=None):
        return abrir_sessao(cenario)

    def turno(self, sessao, mensagem):
        self.mensagens.append(mensagem)
        if "boom" in mensagem:
            raise RuntimeError("timeout ao chamar o modelo\ndetalhe interno")
        RunnableLambda(lambda x: x).with_config(run_name="passo1_mascara").invoke(1)
        RunnableLambda(lambda x: x).with_config(run_name="passo4_nlu").invoke(1)
        buscar_logs.invoke({"servico": "pedidos-api"})
        RunnableLambda(lambda x: x).with_config(run_name="auditoria").invoke(1)
        if "post-mortem" in mensagem:
            fixa = RespostaFixa(
                texto="# Post-mortem\n\nTexto", camada=2, categoria="gerar_relatorio"
            )
            resposta = RespostaTurno(rota="fixa", moderacao={"status": "ok"}, fixa=fixa)
        else:
            resposta = RespostaTurno(
                rota="investigacao",
                moderacao={"status": "ok"},
                analise=_analise(),
                trajetoria=[PassoTrajetoria(ferramenta="buscar_logs", duracao_ms=7, tamanho=2)],
                auditoria=Auditoria(aprovada=False, motivos=["hora divergente"]),
                aviso="Hora divergente",
            )
        self.registro.adicionar(
            RegistroTurno.de_resposta(sessao.session_id, mensagem, resposta, 50)
        )
        return resposta


@pytest.fixture
def agente():
    return AgenteFalso()


@pytest.fixture
def cliente(agente):
    return TestClient(criar_app(obter_agente=lambda: agente, chave_configurada=lambda: True))


def _nova(cliente, cenario="pool_esgotado") -> dict:
    resposta = cliente.post("/api/sessoes", json={"cenario": cenario})
    assert resposta.status_code == 201
    return resposta.json()


def _eventos(texto: str) -> list[tuple[str, dict]]:
    eventos = []
    for bloco in texto.strip().split("\n\n"):
        linhas = dict(linha.split(": ", 1) for linha in bloco.splitlines())
        eventos.append((linhas["event"], json.loads(linhas["data"])))
    return eventos


def test_pagina_inicial_e_estaticos(cliente):
    pagina = cliente.get("/")
    assert pagina.status_code == 200 and "text/html" in pagina.headers["content-type"]
    assert "Nova conversa" in pagina.text
    assert cliente.get("/static/app.css").status_code == 200
    assert cliente.get("/static/app.js").status_code == 200


def test_estado_e_cenarios(cliente):
    estado = cliente.get("/api/estado").json()
    assert estado["chave_configurada"] is True
    ids = {c["id"] for c in cliente.get("/api/cenarios").json()}
    assert "banco_lento_com_deploy" in ids


def test_criar_listar_e_abrir_sessao(cliente):
    criada = _nova(cliente)
    assert criada["cenario"] == "pool_esgotado" and criada["mensagens"] == []
    assert criada["servico"]
    lista = cliente.get("/api/sessoes").json()
    assert [s["id"] for s in lista] == [criada["id"]]
    aberta = cliente.get(f"/api/sessoes/{criada['id']}").json()
    assert aberta["id"] == criada["id"]
    assert cliente.get("/api/sessoes/nao-existe").status_code == 404


def test_cenario_desconhecido_recusado(cliente):
    assert cliente.post("/api/sessoes", json={"cenario": "x"}).status_code == 422


def test_enviar_mensagem_devolve_resposta_estruturada(cliente):
    sessao = _nova(cliente)
    corpo = cliente.post(
        f"/api/sessoes/{sessao['id']}/mensagens", json={"texto": "por que o 500?"}
    ).json()
    assert corpo["papel"] == "agente"
    resposta = corpo["resposta"]
    assert resposta["analise"]["hipoteses"][0]["causa"] == "Deploy v3.2.1"
    assert resposta["analise"]["acoes_sugeridas"][0]["status"] == "sugerida (não executada)"
    assert resposta["aviso"] == "Hora divergente"
    assert corpo["dados_faltantes"] == []  # dado da hipótese secundária não vira pergunta
    assert corpo["fontes"] == ["logs da loja"]
    assert "Deploy v3.2.1" in corpo["texto"]
    aberta = cliente.get(f"/api/sessoes/{sessao['id']}").json()
    assert [m["papel"] for m in aberta["mensagens"]] == ["engenheiro", "agente"]
    assert aberta["titulo"] == "por que o 500?"


def test_mensagem_vazia_recusada(cliente):
    sessao = _nova(cliente)
    url = f"/api/sessoes/{sessao['id']}/mensagens"
    assert cliente.post(url, json={"texto": "   "}).status_code == 422


def test_stream_mostra_passos_reais_e_resposta(cliente):
    sessao = _nova(cliente)
    with cliente.stream(
        "POST", f"/api/sessoes/{sessao['id']}/mensagens/stream", json={"texto": "e o banco?"}
    ) as resposta:
        assert resposta.headers["content-type"].startswith("text/event-stream")
        texto = resposta.read().decode()
    eventos = _eventos(texto)
    passos = [dados["etapa"] for nome, dados in eventos if nome == "passo"]
    assert passos == ["mascarando", "entendendo", "investigando", "consultando", "auditando"]
    consulta = next(d for n, d in eventos if n == "passo" and d["etapa"] == "consultando")
    assert consulta["texto"] == "Consultando logs da loja"
    assert eventos[-1][0] == "resposta"
    assert eventos[-1][1]["resposta"]["aviso"] == "Hora divergente"


def test_erro_do_agente_vira_texto_legivel(cliente):
    sessao = _nova(cliente)
    corpo = cliente.post(f"/api/sessoes/{sessao['id']}/mensagens", json={"texto": "boom"}).json()
    assert corpo["papel"] == "agente" and corpo["resposta"] is None
    assert "RuntimeError: timeout ao chamar o modelo" in corpo["erro"]
    assert "detalhe interno" not in corpo["erro"]
    with cliente.stream(
        "POST", f"/api/sessoes/{sessao['id']}/mensagens/stream", json={"texto": "boom"}
    ) as resposta:
        eventos = _eventos(resposta.read().decode())
    assert eventos[-1][0] == "erro" and "RuntimeError" in eventos[-1][1]["erro"]


def test_postmortem_a_pedido(cliente, agente):
    sessao = _nova(cliente)
    corpo = cliente.post(f"/api/sessoes/{sessao['id']}/postmortem").json()
    assert "post-mortem" in agente.mensagens[-1]
    assert corpo["resposta"]["fixa"]["categoria"] == "gerar_relatorio"


def test_analise_da_sessao(cliente):
    sessao = _nova(cliente)
    outra = _nova(cliente, "rate_limit")
    cliente.post(f"/api/sessoes/{sessao['id']}/mensagens", json={"texto": "p1"})
    cliente.post(f"/api/sessoes/{outra['id']}/mensagens", json={"texto": "p2"})
    turnos = cliente.get(f"/api/sessoes/{sessao['id']}/analise").json()
    assert [t["pergunta"] for t in turnos] == ["p1"]
    assert turnos[0]["auditoria_aprovada"] is False
    assert turnos[0]["trajetoria"][0]["ferramenta"] == "buscar_logs"


def test_sem_chave_recusa_mensagem_com_aviso_legivel(agente):
    cliente = TestClient(criar_app(obter_agente=lambda: agente, chave_configurada=lambda: False))
    assert cliente.get("/api/estado").json()["chave_configurada"] is False
    sessao = _nova(cliente)
    resposta = cliente.post(f"/api/sessoes/{sessao['id']}/mensagens", json={"texto": "oi"})
    assert resposta.status_code == 503
    assert "OPENAI_API_KEY" in resposta.json()["detail"]
    assert agente.mensagens == []
