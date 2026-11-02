"""Pipeline com a investigação do agente: trajetória na resposta, Fase 1 intacta."""

from pathlib import Path

from langchain_core.runnables import RunnableLambda

from agente.agente_react import montar_investigacao_agente
from agente.ferramentas import montar_ferramentas
from agente.loja import FonteLoja
from agente.pipeline import montar_pipeline
from agente.schemas import AnaliseNLU, ResultadoInvestigacao, ResultadoModeracao
from tests.fakes import chamada, roteiro
from tests.test_agente_react import JSON_OK
from tests.test_roteamento import ANALISE

RAIZ = Path(__file__).parent / "dados"


def _nlu(intencao="investigar_erro"):
    return RunnableLambda(lambda estado: AnaliseNLU(intencao=intencao, servico="pagamentos-api"))


def _moderar(texto):
    return ResultadoModeracao(status="ok")


def _pipe(modelo, intencao="investigar_erro"):
    ferr = montar_ferramentas(FonteLoja.gravada("cenario_teste", raiz=RAIZ))
    return montar_pipeline(
        None, _moderar, nlu=_nlu(intencao), investigacao=montar_investigacao_agente(modelo, ferr)
    )


def test_agente_preenche_trajetoria_e_analise():
    modelo = roteiro(chamada("buscar_logs", {"servico": "pagamentos-api"}), JSON_OK)
    resposta = _pipe(modelo).invoke({"mensagem": "pagamentos-api com 500"})
    assert resposta.rota == "investigacao" and resposta.analise is not None
    assert [passo.ferramenta for passo in resposta.trajetoria] == ["buscar_logs"]


def test_erro_do_agente_vira_rota_erro_com_trajetoria():
    modelo = roteiro(chamada("buscar_logs", {"servico": "pagamentos-api"}), "não é json")
    resposta = _pipe(modelo).invoke({"mensagem": "pagamentos-api com 500"})
    assert (
        resposta.rota == "erro"
        and "JSON inválido" in resposta.erro
        and len(resposta.trajetoria) >= 1
    )


def test_resposta_fixa_tem_trajetoria_vazia_e_nao_chama_ferramentas():
    modelo = roteiro(JSON_OK)
    resposta = _pipe(modelo, intencao="saudacao").invoke({"mensagem": "bom dia"})
    assert resposta.rota == "fixa" and resposta.trajetoria == [] and modelo.chamadas == []


def test_texto_mascarado_chega_as_ferramentas():
    fonte = FonteLoja.gravada("cenario_teste", raiz=RAIZ)
    vistos = []

    def espia(base, nova):
        vistos.append((base, nova))
        raise RuntimeError("não importa")

    ferr = montar_ferramentas(fonte, espia)
    modelo = roteiro(chamada("comparar_versoes", {"tag_base": "a", "tag_nova": "b"}), JSON_OK)
    pipeline = montar_pipeline(
        None, _moderar, nlu=_nlu(), investigacao=montar_investigacao_agente(modelo, ferr)
    )
    pipeline.invoke({"mensagem": "erro com token=abc123segredo no pagamentos-api"})
    enviado = " ".join(str(mensagem.content) for mensagem in modelo.chamadas[0])
    assert "abc123segredo" not in enviado and "[SEGREDO]" in enviado


def test_fase1_str_e_analise_continuam_aceitas():
    for resultado in ("falhou", ANALISE):
        pipeline = montar_pipeline(
            None,
            _moderar,
            nlu=_nlu(),
            investigacao=RunnableLambda(lambda estado, resposta=resultado: resposta),
        )
        resposta = pipeline.invoke({"mensagem": "erro"})
        assert resposta.rota == ("erro" if isinstance(resultado, str) else "investigacao")
        assert resposta.trajetoria == []


def test_resultado_investigacao_direto():
    pipeline = montar_pipeline(
        None,
        _moderar,
        nlu=_nlu(),
        investigacao=RunnableLambda(lambda estado: ResultadoInvestigacao(erro="x")),
    )
    resposta = pipeline.invoke({"mensagem": "erro"})
    assert resposta.rota == "erro" and resposta.erro == "x"
