"""Roteamento do pipeline com NLU, moderação e investigação falsos (sem rede)."""

import pytest
from langchain_core.runnables import RunnableLambda

from agente.pipeline import montar_pipeline
from agente.schemas import AnaliseIncidente, AnaliseNLU, Hipotese, ResultadoModeracao

ANALISE = AnaliseIncidente(
    severidade="alta",
    categoria="null_pointer",
    servico="pagamentos-api",
    resumo="NPE",
    hipoteses=[
        Hipotese(causa="cupom nulo", confianca=0.8, evidencia="NullPointerException"),
        Hipotese(causa="deploy recente", confianca=0.5, evidencia="depois do deploy"),
        Hipotese(
            causa="pool esgotado",
            confianca=0.1,
            evidencia_insuficiente=True,
            dado_que_falta="métrica do pool",
        ),
    ],
    proximos_passos=["ver deploy"],
)


class Espioes:
    """Registra o que cada componente falso recebeu."""

    def __init__(self, intencao="investigar_erro", moderacao="ok"):
        self.nlu_msgs, self.inv_estados, self.mod_textos = [], [], []
        self.intencao, self.moderacao = intencao, moderacao

    def nlu(self):
        def f(entrada):
            self.nlu_msgs.append(entrada["mensagem"])
            return AnaliseNLU(intencao=self.intencao, servico="pagamentos-api")

        return RunnableLambda(f)

    def moderar(self, texto):
        self.mod_textos.append(texto)
        return ResultadoModeracao(status=self.moderacao)

    def investigacao(self):
        def f(estado):
            self.inv_estados.append(estado)
            return ANALISE

        return RunnableLambda(f)


def _pipe(espioes):
    return montar_pipeline(
        None, espioes.moderar, nlu=espioes.nlu(), investigacao=espioes.investigacao()
    )


@pytest.mark.parametrize("mensagem", ["", "   \n"])
def test_mensagem_vazia_vai_para_fixa(mensagem):
    espioes = Espioes()
    resposta = _pipe(espioes).invoke({"mensagem": mensagem})
    assert (
        resposta.rota == "fixa" and resposta.fixa.categoria == "vazia" and resposta.fixa.camada == 2
    )
    assert espioes.nlu_msgs == [] and espioes.inv_estados == []


def test_saudacao_nao_chama_investigacao():
    espioes = Espioes(intencao="saudacao")
    resposta = _pipe(espioes).invoke({"mensagem": "bom dia"})
    assert (
        resposta.rota == "fixa"
        and resposta.fixa.camada == 2
        and resposta.fixa.categoria == "saudacao"
    )
    assert resposta.nlu.intencao == "saudacao"
    assert espioes.inv_estados == []


def test_investigar_erro_vai_para_investigacao():
    espioes = Espioes()
    resposta = _pipe(espioes).invoke({"mensagem": "NullPointerException no pagamentos-api"})
    assert resposta.rota == "investigacao" and resposta.analise == ANALISE
    assert len(espioes.inv_estados) == 1


def test_moderacao_aviso_segue_para_investigacao():
    """Ex.: 'OOMKilled' marcado como violence abaixo do limiar: registra e segue."""
    espioes = Espioes(moderacao="aviso")
    resposta = _pipe(espioes).invoke({"mensagem": "o container levou OOMKilled"})
    assert resposta.rota == "investigacao" and resposta.moderacao.status == "aviso"
    assert len(espioes.nlu_msgs) == 1 and len(espioes.inv_estados) == 1


def test_moderacao_sinalizada_nao_chama_nlu():
    espioes = Espioes(moderacao="sinalizada")
    resposta = _pipe(espioes).invoke({"mensagem": "algo impróprio"})
    assert resposta.rota == "fixa" and resposta.fixa.camada == 1
    assert resposta.nlu is None and espioes.nlu_msgs == [] and espioes.inv_estados == []


def test_textos_chegam_mascarados():
    espioes = Espioes()
    _pipe(espioes).invoke({"mensagem": "erro com senha=abc12345 de ana@loja.com"})
    for texto in (*espioes.mod_textos, *espioes.nlu_msgs, espioes.inv_estados[0]["mensagem"]):
        assert "abc12345" not in texto and "ana@loja.com" not in texto
        assert "[SEGREDO]" in texto and "[EMAIL]" in texto


def test_batch_e_historico_opcional():
    espioes = Espioes()
    respostas = _pipe(espioes).batch([{"mensagem": "a"}, {"mensagem": "b", "historico": []}])
    assert [resposta.rota for resposta in respostas] == ["investigacao", "investigacao"]


def test_json_invalido_duas_vezes_vira_erro():
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    espioes = Espioes()
    llm = FakeListChatModel(responses=["isto não é json", "nem isto"])
    pipeline = montar_pipeline(llm, espioes.moderar, nlu=espioes.nlu())
    resposta = pipeline.invoke({"mensagem": "NullPointerException no pagamentos-api"})
    assert resposta.rota == "erro" and resposta.erro and resposta.analise is None


def test_json_valido_com_llm_falso_gera_analise():
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    espioes = Espioes()
    llm = FakeListChatModel(responses=[ANALISE.model_dump_json()])
    pipeline = montar_pipeline(llm, espioes.moderar, nlu=espioes.nlu())
    resposta = pipeline.invoke({"mensagem": "NullPointerException no pagamentos-api"})
    assert resposta.rota == "investigacao" and resposta.analise.severidade == "alta"


def test_json_invalido_na_primeira_e_valido_na_segunda():
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    espioes = Espioes()
    llm = FakeListChatModel(responses=["lixo", ANALISE.model_dump_json()])
    pipeline = montar_pipeline(llm, espioes.moderar, nlu=espioes.nlu())
    assert pipeline.invoke({"mensagem": "erro"}).rota == "investigacao"


def test_json_invalido_inclui_mensagem_mascarada_no_erro():
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    espioes = Espioes()
    llm = FakeListChatModel(responses=["lixo", "lixo"])
    pipeline = montar_pipeline(llm, espioes.moderar, nlu=espioes.nlu())
    resposta = pipeline.invoke({"mensagem": "falha com senha=abc12345"})
    assert resposta.rota == "erro" and "JSON inválido da investigação:" in resposta.erro
    assert (
        "| mensagem: falha com senha=[SEGREDO]" in resposta.erro and "abc12345" not in resposta.erro
    )


@pytest.mark.parametrize(
    "intencao",
    [
        "pedido_de_acao",
        "tentativa_de_injecao",
        "gerar_relatorio",
        "confirmar_causa",
        "fora_do_escopo",
        "conteudo_proibido",
    ],
)
def test_categorias_fixas_camada_2_com_texto_proprio(intencao):
    espioes = Espioes(intencao=intencao)
    resposta = _pipe(espioes).invoke({"mensagem": "x"})
    assert (
        resposta.rota == "fixa"
        and resposta.fixa.camada == 2
        and resposta.fixa.categoria == intencao
    )
    assert not resposta.fixa.texto.startswith("[resposta fixa") and espioes.inv_estados == []


def test_texto_fora_do_escopo_e_fase_futura():
    from agente.pipeline import _texto_fixo

    assert "Só ajudo a investigar incidentes de produção." in _texto_fixo("fora_do_escopo")
    assert "Fase 5" in _texto_fixo("gerar_relatorio")
    assert "Fase 3" in _texto_fixo("confirmar_causa")
