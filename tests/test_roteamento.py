"""Roteamento do pipeline com NLU, moderação e investigação falsos (sem rede)."""
import pytest
from langchain_core.runnables import RunnableLambda

from agente.pipeline import montar_pipeline
from agente.schemas import AnaliseIncidente, AnaliseNLU, Hipotese, ResultadoModeracao

ANALISE = AnaliseIncidente(
    severidade="alta", categoria="null_pointer", servico="pagamentos-api", resumo="NPE",
    hipoteses=[
        Hipotese(causa="cupom nulo", confianca=0.8, evidencia="NullPointerException"),
        Hipotese(causa="deploy recente", confianca=0.5, evidencia="depois do deploy"),
        Hipotese(causa="pool esgotado", confianca=0.1, evidencia_insuficiente=True,
                 dado_que_falta="métrica do pool"),
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


def _pipe(esp):
    return montar_pipeline(None, esp.moderar, nlu=esp.nlu(), investigacao=esp.investigacao())


@pytest.mark.parametrize("msg", ["", "   \n"])
def test_mensagem_vazia_vai_para_fixa(msg):
    esp = Espioes()
    r = _pipe(esp).invoke({"mensagem": msg})
    assert r.rota == "fixa" and r.fixa.categoria == "vazia" and r.fixa.camada == 2
    assert esp.nlu_msgs == [] and esp.inv_estados == []


def test_saudacao_nao_chama_investigacao():
    esp = Espioes(intencao="saudacao")
    r = _pipe(esp).invoke({"mensagem": "bom dia"})
    assert r.rota == "fixa" and r.fixa.camada == 2 and r.fixa.categoria == "saudacao"
    assert r.nlu.intencao == "saudacao"
    assert esp.inv_estados == []


def test_investigar_erro_vai_para_investigacao():
    esp = Espioes()
    r = _pipe(esp).invoke({"mensagem": "NullPointerException no pagamentos-api"})
    assert r.rota == "investigacao" and r.analise == ANALISE
    assert len(esp.inv_estados) == 1


def test_moderacao_aviso_segue_para_investigacao():
    """Ex.: 'OOMKilled' marcado como violence abaixo do limiar: registra e segue."""
    esp = Espioes(moderacao="aviso")
    r = _pipe(esp).invoke({"mensagem": "o container levou OOMKilled"})
    assert r.rota == "investigacao" and r.moderacao.status == "aviso"
    assert len(esp.nlu_msgs) == 1 and len(esp.inv_estados) == 1


def test_moderacao_sinalizada_nao_chama_nlu():
    esp = Espioes(moderacao="sinalizada")
    r = _pipe(esp).invoke({"mensagem": "algo impróprio"})
    assert r.rota == "fixa" and r.fixa.camada == 1
    assert r.nlu is None and esp.nlu_msgs == [] and esp.inv_estados == []


def test_textos_chegam_mascarados():
    esp = Espioes()
    _pipe(esp).invoke({"mensagem": "erro com senha=abc12345 de ana@loja.com"})
    for texto in (*esp.mod_textos, *esp.nlu_msgs, esp.inv_estados[0]["mensagem"]):
        assert "abc12345" not in texto and "ana@loja.com" not in texto
        assert "[SEGREDO]" in texto and "[EMAIL]" in texto


def test_batch_e_historico_opcional():
    esp = Espioes()
    rs = _pipe(esp).batch([{"mensagem": "a"}, {"mensagem": "b", "historico": []}])
    assert [r.rota for r in rs] == ["investigacao", "investigacao"]


def test_json_invalido_duas_vezes_vira_erro():
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    esp = Espioes()
    llm = FakeListChatModel(responses=["isto não é json", "nem isto"])
    pipe = montar_pipeline(llm, esp.moderar, nlu=esp.nlu())
    r = pipe.invoke({"mensagem": "NullPointerException no pagamentos-api"})
    assert r.rota == "erro" and r.erro and r.analise is None


def test_json_valido_com_llm_falso_gera_analise():
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    esp = Espioes()
    llm = FakeListChatModel(responses=[ANALISE.model_dump_json()])
    pipe = montar_pipeline(llm, esp.moderar, nlu=esp.nlu())
    r = pipe.invoke({"mensagem": "NullPointerException no pagamentos-api"})
    assert r.rota == "investigacao" and r.analise.severidade == "alta"


def test_json_invalido_na_primeira_e_valido_na_segunda():
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    esp = Espioes()
    llm = FakeListChatModel(responses=["lixo", ANALISE.model_dump_json()])
    pipe = montar_pipeline(llm, esp.moderar, nlu=esp.nlu())
    assert pipe.invoke({"mensagem": "erro"}).rota == "investigacao"


def test_json_invalido_inclui_mensagem_mascarada_no_erro():
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    esp = Espioes()
    llm = FakeListChatModel(responses=["lixo", "lixo"])
    pipe = montar_pipeline(llm, esp.moderar, nlu=esp.nlu())
    r = pipe.invoke({"mensagem": "falha com senha=abc12345"})
    assert r.rota == "erro" and "JSON inválido da investigação:" in r.erro
    assert "| mensagem: falha com senha=[SEGREDO]" in r.erro and "abc12345" not in r.erro


@pytest.mark.parametrize("intencao", [
    "pedido_de_acao", "tentativa_de_injecao", "gerar_relatorio", "confirmar_causa",
    "fora_do_escopo", "conteudo_proibido",
])
def test_categorias_fixas_camada_2_com_texto_proprio(intencao):
    esp = Espioes(intencao=intencao)
    r = _pipe(esp).invoke({"mensagem": "x"})
    assert r.rota == "fixa" and r.fixa.camada == 2 and r.fixa.categoria == intencao
    assert not r.fixa.texto.startswith("[resposta fixa") and esp.inv_estados == []


def test_texto_fora_do_escopo_e_fase_futura():
    from agente.pipeline import _texto_fixo
    assert "Só ajudo a investigar incidentes de produção." in _texto_fixo("fora_do_escopo")
    assert "Fase 5" in _texto_fixo("gerar_relatorio")
    assert "Fase 3" in _texto_fixo("confirmar_causa")
