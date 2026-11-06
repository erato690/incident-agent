"""Travas de qualidade ligadas ao pipeline: NLU saneado e análise sem consulta repetida."""

from langchain_core.runnables import RunnableLambda

from agente.pipeline import montar_pipeline
from agente.schemas import (
    AcaoSugerida,
    AnaliseNLU,
    PassoTrajetoria,
    ResultadoInvestigacao,
    ResultadoModeracao,
)
from tests.test_roteamento import ANALISE

PERGUNTA = "O pagamentos-api está com erros desde as 14h. Qual a causa provável?"


def _pipe(nlu, investigacao):
    return montar_pipeline(
        None, lambda texto: ResultadoModeracao(status="ok"), nlu=nlu, investigacao=investigacao
    )


def test_nlu_com_a_causa_como_dado_faltante_sai_sem_o_dado():
    nlu = RunnableLambda(
        lambda e: AnaliseNLU(
            intencao="investigar_erro",
            servico="pagamentos-api",
            dado_faltante="causa provável dos erros",
        )
    )
    resposta = _pipe(nlu, RunnableLambda(lambda e: ANALISE)).invoke({"mensagem": PERGUNTA})
    assert resposta.nlu.dado_faltante is None and resposta.nlu.servico == "pagamentos-api"


def test_investigacao_sem_passo_ou_acao_que_repete_consulta_feita():
    analise = ANALISE.model_copy(
        update={
            "proximos_passos": ["Verifique os logs do pagamentos-api.", "Enfileirar pagamentos."],
            "acoes_sugeridas": [
                AcaoSugerida(acao="Consulte o limite documentado", motivo="m", risco="baixo"),
                AcaoSugerida(acao="Respeitar o Retry-After de 30 s", motivo="m", risco="baixo"),
            ],
        }
    )
    trajetoria = [PassoTrajetoria(ferramenta="buscar_logs", duracao_ms=1, tamanho=1)]
    investigacao = RunnableLambda(
        lambda e: ResultadoInvestigacao(analise=analise, trajetoria=trajetoria)
    )
    nlu = RunnableLambda(lambda e: AnaliseNLU(intencao="investigar_erro"))
    resposta = _pipe(nlu, investigacao).invoke({"mensagem": PERGUNTA})
    assert resposta.analise.proximos_passos == ["Enfileirar pagamentos."]
    assert [a.acao for a in resposta.analise.acoes_sugeridas] == ["Respeitar o Retry-After de 30 s"]
