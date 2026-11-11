"""Pipeline com memória: confirmar_causa vai ao Registrador; sem memória, resposta fixa."""

import json
import re
from datetime import datetime
from pathlib import Path

from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.runnables import RunnableLambda

from agente.agente_react import montar_investigador, montar_registrador
from agente.bateria import memoria_consultada
from agente.ferramentas import montar_ferramentas
from agente.loja import FonteLoja
from agente.memoria import MemoriaLongoPrazo
from agente.pipeline import montar_pipeline
from agente.schemas import AnaliseNLU, Episodio, ResolucaoMemoria, ResultadoModeracao
from tests.fakes import chamada, roteiro
from tests.test_agente_react import JSON_OK
from tests.test_roteamento import ANALISE

AGORA = datetime(2026, 11, 2, 12, 0)
RAIZ = Path(__file__).parent / "dados"


def _nlu(intencao="confirmar_causa", servico="pedidos-api"):
    return RunnableLambda(lambda estado: AnaliseNLU(intencao=intencao, servico=servico))


def _memoria():
    return MemoriaLongoPrazo(DeterministicFakeEmbedding(size=64), agora=lambda: AGORA)


def _resolvedor(acao="inserir_novo"):
    def decide(entrada):
        antigo = re.search(r"ID: (\S+)", entrada["existentes"]).group(1)
        return ResolucaoMemoria(acao=acao, id_memoria_antiga=antigo, motivo="decisão do teste")

    return RunnableLambda(decide)


def _gravacao(causa="deploy v3.2.0", agente=False):
    argumentos = {
        "resumo": "500 no checkout; deploy às 13:40",
        "causa": causa,
        "evidencia": "métricas",
        "levantada_pelo_agente": agente,
    }
    return chamada("gravar_episodio", argumentos)


def _pipe(memoria, nlu=None, modelo=None, resolvedor=None, investigacao=None):
    resolvedor = resolvedor or _resolvedor()
    ferramentas = montar_ferramentas(
        FonteLoja.gravada("cenario_teste", raiz=RAIZ), memoria=memoria, resolver=resolvedor
    )
    registro = montar_registrador(modelo or roteiro(_gravacao(), "Registrei."), ferramentas)
    return montar_pipeline(
        None,
        lambda texto: ResultadoModeracao(status="ok"),
        nlu=nlu or _nlu(),
        investigacao=investigacao or RunnableLambda(lambda estado: ANALISE),
        memoria=memoria,
        registro=registro,
    )


def _turno(
    pipe,
    mensagem="confirmado: foi o deploy v3.2.0",
    incidente_id="inc-1",
    session_id="t-1",
    **extra,
):
    entrada = {"mensagem": mensagem, "incidente_id": incidente_id, "session_id": session_id}
    return pipe.invoke({**entrada, **extra})


def test_sem_memoria_confirmar_causa_continua_fixa():
    pipe = montar_pipeline(
        None,
        lambda texto: ResultadoModeracao(status="ok"),
        nlu=_nlu(),
        investigacao=RunnableLambda(lambda estado: ANALISE),
    )
    resposta = pipe.invoke({"mensagem": "confirmado: foi o deploy"})
    assert resposta.rota == "fixa" and resposta.fixa.categoria == "confirmar_causa"
    assert "Fase 3" in resposta.fixa.texto and resposta.episodio is None


def test_confirmacao_vai_ao_agente_de_registro_e_responde_rota_memoria():
    memoria = _memoria()
    resposta = _turno(_pipe(memoria), session_id="t-9")
    assert resposta.rota == "memoria" and resposta.episodio.causa == "deploy v3.2.0"
    assert (resposta.episodio.incidente_id, resposta.episodio.session_id) == ("inc-1", "t-9")
    assert resposta.episodio.servico == "pedidos-api" and resposta.episodio_anterior is None
    assert resposta.resolucao.acao == "inserir_novo" and resposta.episodio.origem == "engenheiro"
    assert "Causa registrada" in resposta.fixa.texto
    assert memoria.consultar_episodios("pedidos-api", "deploy v3.2.0")


def test_origem_agente_quando_levantada_pelo_agente():
    modelo = roteiro(_gravacao(agente=True), "ok")
    assert _turno(_pipe(_memoria(), modelo=modelo)).episodio.origem == "agente"


def test_sem_servico_pede_o_servico_sem_chamar_o_agente():
    memoria = _memoria()
    modelo = roteiro(_gravacao(), "ok")
    resposta = _turno(_pipe(memoria, nlu=_nlu(servico=None), modelo=modelo))
    assert resposta.rota == "fixa" and resposta.fixa.categoria == "pedir_servico"
    assert modelo.chamadas == [] and memoria.listar_episodios("pedidos-api") == []


def test_sem_incidente_id_pede_o_incidente():
    modelo = roteiro(_gravacao(), "ok")
    entrada = {"mensagem": "confirmado: foi o deploy", "session_id": "t-1"}
    resposta = _pipe(_memoria(), modelo=modelo).invoke(entrada)
    assert resposta.rota == "fixa" and resposta.fixa.categoria == "pedir_incidente"
    assert modelo.chamadas == [] and resposta.episodio is None


def test_sem_session_id_pede_a_sessao_sem_chamar_o_agente():
    memoria = _memoria()
    modelo = roteiro(_gravacao(), "ok")
    entrada = {"mensagem": "confirmado: foi o deploy", "incidente_id": "inc-1"}
    resposta = _pipe(memoria, modelo=modelo).invoke(entrada)
    assert resposta.rota == "fixa" and resposta.fixa.categoria == "pedir_sessao"
    assert "sessão" in resposta.fixa.texto
    assert modelo.chamadas == [] and memoria.listar_episodios("pedidos-api") == []


def test_erro_do_resolvedor_nao_grava_e_responde_rota_erro_legivel():
    def quebra(entrada):
        raise RuntimeError("resolvedor fora do ar")

    memoria = _memoria()
    _turno(_pipe(memoria))
    pipe = _pipe(
        memoria, modelo=roteiro(_gravacao("outra causa"), "ok"), resolvedor=RunnableLambda(quebra)
    )
    resposta = _turno(pipe)
    assert resposta.rota == "erro" and resposta.episodio is None
    assert "nada foi registrado" in resposta.erro and "resolvedor fora do ar" in resposta.erro
    assert [e.causa for e in memoria.listar_episodios("pedidos-api")] == ["deploy v3.2.0"]


def test_agente_de_registro_grava_trajetoria_e_a_resposta_a_traz():
    consulta = chamada("consultar_memoria", {"servico": "pedidos-api", "descricao": "x"}, "c0")
    modelo = roteiro(consulta, _gravacao(), "Registrei.")
    resposta = _turno(_pipe(_memoria(), modelo=modelo))
    assert resposta.rota == "memoria"
    assert [p.ferramenta for p in resposta.trajetoria] == ["consultar_memoria", "gravar_episodio"]
    assert memoria_consultada(resposta)


def test_troca_de_causa_arquiva_o_anterior_e_avisa():
    memoria = _memoria()
    _turno(_pipe(memoria))
    modelo = roteiro(_gravacao("limite de memória"), "ok")
    pipe = _pipe(memoria, modelo=modelo, resolvedor=_resolvedor("atualizar_existente"))
    resposta = _turno(pipe)
    assert resposta.episodio_anterior.causa == "deploy v3.2.0"
    assert resposta.episodio_anterior.status == "arquivado"
    assert resposta.episodio.causa == "limite de memória"
    assert resposta.episodio.substitui == resposta.episodio_anterior.id_memoria
    assert resposta.resolucao.acao == "atualizar_existente"
    assert "deploy v3.2.0" in resposta.fixa.texto and "limite de memória" in resposta.fixa.texto
    assert len(memoria.listar_episodios("pedidos-api")) == 2


def test_pergunta_nao_registra():
    memoria = _memoria()
    pipe = _pipe(memoria, nlu=_nlu("investigar_erro"))
    resposta = _turno(pipe, "será que foi o deploy?")
    assert resposta.rota == "investigacao" and resposta.episodio is None
    assert memoria.listar_episodios("pedidos-api") == []


def test_agente_de_investigacao_tentando_gravar_hipotese_e_recusado_no_pipeline():
    memoria = _memoria()
    ferramentas = montar_ferramentas(
        FonteLoja.gravada("cenario_teste", raiz=RAIZ), memoria=memoria, resolver=_resolvedor()
    )
    modelo = roteiro(_gravacao("acho que foi o deploy"), JSON_OK)
    investigacao = montar_investigador(modelo, ferramentas)
    pipe = _pipe(memoria, nlu=_nlu("investigar_erro"), investigacao=investigacao)
    resposta = _turno(pipe, "acho que foi o deploy, grava isso")
    assert resposta.rota == "investigacao" and resposta.episodio is None
    assert resposta.trajetoria[0].ferramenta == "gravar_episodio"
    assert memoria.listar_episodios("pedidos-api") == []


def test_incidente_id_e_session_id_passam_pela_mascara():
    resposta = _turno(
        _pipe(_memoria()), incidente_id="inc-token=abc123", session_id="t-senha=xyz789"
    )
    assert "abc123" not in resposta.episodio.incidente_id
    assert "xyz789" not in resposta.episodio.session_id


def test_segredo_na_mensagem_nao_chega_ao_modelo_de_registro():
    modelo = roteiro(_gravacao(), "ok")
    _turno(_pipe(_memoria(), modelo=modelo), "confirmado: token=abc123 vazou")
    assert all("abc123" not in str(msg.content) for msg in modelo.chamadas[0])


def test_modelo_que_nao_chama_gravar_episodio_vira_rota_erro_legivel():
    memoria = _memoria()
    resposta = _turno(_pipe(memoria, modelo=roteiro("Pronto, registrei.")))
    assert resposta.rota == "erro" and resposta.episodio is None
    assert "gravar" in resposta.erro and "nada foi registrado" in resposta.erro
    assert memoria.listar_episodios("pedidos-api") == []


def test_falha_do_agente_de_registro_vira_rota_erro():
    def quebra(estado):
        raise RuntimeError("modelo fora do ar")

    pipe = montar_pipeline(
        None,
        lambda texto: ResultadoModeracao(status="ok"),
        nlu=_nlu(),
        investigacao=RunnableLambda(lambda estado: ANALISE),
        memoria=_memoria(),
        registro=RunnableLambda(quebra),
    )
    resposta = _turno(pipe)
    assert resposta.rota == "erro" and "modelo fora do ar" in resposta.erro
    assert resposta.episodio is None


def test_gravacao_recusada_pela_trava_nao_vira_rota_memoria():
    modelo = roteiro(_gravacao(), "ok")
    pipe = _pipe(_memoria(), nlu=_nlu("investigar_erro"), modelo=modelo)
    assert _turno(pipe).rota == "investigacao"
    assert modelo.chamadas == []


# --- Citação do incidente parecido: id e data na evidência, sem depender do modelo ------

ANALISE_POOL = {
    "severidade": "alta",
    "categoria": "banco",
    "servico": "pedidos-api",
    "resumo": "500 no pedidos-api com o pool de conexões no limite",
    "hipoteses": [
        {
            "causa": "deploy v3.2.0 reduziu o pool de conexões para 10",
            "confianca": 0.9,
            "evidencia": "buscar_logs: HikariPool-1 Connection is not available (x284)",
        },
        {
            "causa": "gateway de pagamento lento",
            "confianca": 0.1,
            "evidencia": None,
            "evidencia_insuficiente": True,
            "dado_que_falta": "latência do gateway",
        },
    ],
    "proximos_passos": ["Conferir o pool_max"],
}


def _memoria_com_episodio_de_pool():
    memoria = _memoria()
    memoria._gravar_episodio(
        Episodio(
            incidente_id="inc-2026-09-03-pedidos",
            servico="pedidos-api",
            causa="Pool de conexões esgotado: um deploy reduziu o pool_max de 20 para 10.",
            resumo="500 no checkout",
            criado_em=datetime(2026, 9, 3, 14, 30),
            origem="engenheiro",
            session_id="t-antiga",
        )
    )
    return memoria


def _investigador_que_consulta(memoria, consultar=True):
    ferramentas = montar_ferramentas(FonteLoja.gravada("cenario_teste", raiz=RAIZ), memoria=memoria)
    memoria_ = chamada("consultar_memoria", {"servico": "pedidos-api", "descricao": "HikariPool"})
    # sem consultar a memória, o agente ainda observa (os logs): concluir sem ferramenta não vale
    logs = chamada("buscar_logs", {"servico": "pedidos-api"})
    modelo = roteiro(memoria_ if consultar else logs, json.dumps(ANALISE_POOL))
    return montar_investigador(modelo, ferramentas)


def _hipoteses(memoria, consultar=True):
    pipe = _pipe(
        memoria,
        nlu=_nlu("investigar_erro"),
        investigacao=_investigador_que_consulta(memoria, consultar),
    )
    resposta = _turno(pipe, mensagem="o pedidos-api voltou a dar 500")
    return resposta.analise.hipoteses


def test_episodio_consultado_entra_na_evidencia_da_hipotese_correspondente():
    principal, outra = _hipoteses(_memoria_com_episodio_de_pool())
    assert "buscar_logs: HikariPool-1" in principal.evidencia
    assert (
        "consultar_memoria: incidente inc-2026-09-03-pedidos em 2026-09-03" in principal.evidencia
    )
    assert "histórico, não é observação atual" in principal.evidencia
    assert outra.evidencia is None


def test_sem_consultar_memoria_a_evidencia_fica_como_o_modelo_escreveu():
    principal, _ = _hipoteses(_memoria_com_episodio_de_pool(), consultar=False)
    assert principal.evidencia == ANALISE_POOL["hipoteses"][0]["evidencia"]


def test_episodio_abaixo_do_limiar_nao_entra_na_evidencia(monkeypatch):
    monkeypatch.setattr(MemoriaLongoPrazo.consultar_episodios, "__defaults__", (3, 1.01))
    principal, _ = _hipoteses(_memoria_com_episodio_de_pool())
    assert "consultar_memoria" not in principal.evidencia


def test_id_ja_citado_pelo_modelo_nao_se_repete():
    citada = "consultar_memoria: incidente inc-2026-09-03-pedidos em 2026-09-03: pool"
    ANALISE_POOL["hipoteses"][0]["evidencia"] += f"; {citada}"
    try:
        principal, _ = _hipoteses(_memoria_com_episodio_de_pool())
    finally:
        ANALISE_POOL["hipoteses"][0]["evidencia"] = ANALISE_POOL["hipoteses"][0]["evidencia"][
            : -len(f"; {citada}")
        ]
    assert principal.evidencia.count("inc-2026-09-03-pedidos") == 1
