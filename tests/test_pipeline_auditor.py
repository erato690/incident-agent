"""Auditor no pipeline: depois da investigação, só na rota "investigacao"."""

from langchain_core.runnables import RunnableLambda

from agente.pipeline import montar_etapas, montar_pipeline
from agente.schemas import (
    AnaliseNLU,
    Auditoria,
    PassoTrajetoria,
    ResultadoInvestigacao,
    ResultadoModeracao,
)
from tests.test_roteamento import ANALISE

PASSO = PassoTrajetoria(ferramenta="f", duracao_ms=1, tamanho=2, observacao="obs")


def _auditor(aprovada, recebidos):
    def audita(entrada):
        recebidos.append(entrada)
        motivos = [] if aprovada else ["número inventado", "versão inexistente"]
        return Auditoria(aprovada=aprovada, motivos=motivos)

    return RunnableLambda(audita)


def _pipe(auditor, investigacao=None, intencao="investigar_erro"):
    return montar_pipeline(
        None,
        lambda texto: ResultadoModeracao(status="ok"),
        nlu=RunnableLambda(lambda estado: AnaliseNLU(intencao=intencao)),
        investigacao=investigacao
        or RunnableLambda(lambda e: ResultadoInvestigacao(analise=ANALISE, trajetoria=[PASSO])),
        auditor=auditor,
    )


def _roda(pipe, mensagem="erro 500 no pagamentos-api"):
    return pipe.invoke({"mensagem": mensagem, "historico": []})


def test_aprovada_grava_auditoria_sem_aviso_e_recebe_analise_trajetoria_e_mensagem():
    recebidos = []
    resposta = _roda(_pipe(_auditor(True, recebidos)))
    assert resposta.auditoria.aprovada and resposta.aviso is None
    assert recebidos[0]["analise"] == ANALISE and recebidos[0]["trajetoria"] == [PASSO]
    assert recebidos[0]["mensagem"] == "erro 500 no pagamentos-api"
    assert resposta.rota == "investigacao" and resposta.analise == ANALISE  # resposta preservada


def test_reprovada_sai_com_aviso_e_motivos_sem_nova_tentativa():
    chamadas = []
    investigacao = RunnableLambda(
        lambda e: chamadas.append(1) or ResultadoInvestigacao(analise=ANALISE)
    )
    resposta = _roda(_pipe(_auditor(False, []), investigacao))
    assert resposta.aviso == (
        "Resposta reprovada pelo auditor: número inventado; versão inexistente"
    )
    assert not resposta.auditoria.aprovada and resposta.analise == ANALISE
    assert len(chamadas) == 1


def test_fora_da_rota_investigacao_o_auditor_nao_roda():
    recebidos = []
    pipe = _pipe(_auditor(False, recebidos), intencao="saudacao")
    resposta = _roda(pipe, "oi")
    assert recebidos == [] and resposta.auditoria is None and resposta.aviso is None
    erro = _roda(_pipe(_auditor(False, recebidos), RunnableLambda(lambda e: "falhou")))
    assert recebidos == [] and erro.rota == "erro" and erro.auditoria is None


def test_sem_auditor_nada_muda_e_etapa_nomeada_so_com_auditor():
    nulo = RunnableLambda(lambda e: e)
    args = (None, lambda t: ResultadoModeracao(status="ok"), nulo, nulo)
    sem = montar_etapas(*args)
    com = montar_etapas(*args, auditor=_auditor(True, []))
    assert "passo6b_auditoria" not in sem
    nomes = list(com)
    assert nomes[nomes.index("passo6b_auditoria") - 1] == "passo6_investigacao"
    assert com["passo6b_auditoria"].name == "passo6b_auditoria"
    assert _roda(_pipe(None)).auditoria is None
