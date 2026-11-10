"""Pergunta aberta sem serviço ("tem alguma coisa com problema?"): visão geral com as
ferramentas, serviço da sessão, nada de "sistema normal" sem observação e 1 hipótese sem erro."""

import json
from pathlib import Path

from langchain_core.runnables import RunnableLambda

from agente.agente_react import SISTEMA_AGENTE, montar_investigador
from agente.conversa import abrir_sessao, montar_conversa
from agente.ferramentas import montar_ferramentas
from agente.loja import FonteLoja, servico_do_cenario
from agente.pipeline import montar_pipeline
from agente.schemas import AnaliseIncidente, AnaliseNLU, ResultadoInvestigacao, ResultadoModeracao
from tests.fakes import chamada, roteiro

RAIZ = Path(__file__).parent / "dados"
UMA_HIPOTESE = {
    "severidade": "media",
    "categoria": "desconhecida",
    "resumo": "Sintoma sem serviço definido",
    "hipoteses": [
        {
            "causa": "sintoma desconhecido",
            "confianca": 0.2,
            "evidencia_insuficiente": True,
            "dado_que_falta": "erros nos serviços",
        }
    ],
    "proximos_passos": ["corrigir a causa quando identificada"],
}
SISTEMA_NORMAL = {
    "severidade": "baixa",
    "categoria": "nenhuma",
    "resumo": "Sistema funcionando normalmente",
    "hipoteses": [
        {
            "causa": "Sistema funcionando normalmente",
            "confianca": 0.9,
            "evidencia": "Nenhuma evidência de erro nos logs",
        },
        {
            "causa": "falha intermitente",
            "confianca": 0.1,
            "evidencia_insuficiente": True,
            "dado_que_falta": "horário do sintoma",
        },
    ],
    "proximos_passos": ["manter o monitoramento"],
}


def _ferramentas():
    return montar_ferramentas(FonteLoja.gravada("cenario_teste", raiz=RAIZ))


def _nlu(servico=None, dado=None):
    return AnaliseNLU(intencao="investigar_erro", servico=servico, dado_faltante=dado)


# --- Visão geral: logs e métricas sem serviço ------------------------------------------------


def test_logs_sem_servico_trazem_todos_os_servicos():
    fonte = FonteLoja.gravada("cenario_teste", raiz=RAIZ)
    servicos = {registro["servico"] for registro in fonte.logs(None)["logs"]}
    assert len(servicos) >= 2
    assert fonte.logs(None)["total"] >= fonte.logs("pagamentos-api")["total"]
    assert fonte.metricas(None)


def test_ferramentas_de_logs_e_metricas_aceitam_visao_geral():
    ferramentas = {f.name: f for f in _ferramentas()}
    for nome in ("buscar_logs", "buscar_metricas"):
        assert "servico" not in ferramentas[nome].tool_call_schema.model_json_schema().get(
            "required", []
        )
    assert "pagamentos-api" in ferramentas["buscar_logs"].invoke({})


def test_servico_do_cenario_vem_do_arquivo_gravado():
    assert servico_do_cenario("pool_esgotado") == "pedidos-api"
    assert servico_do_cenario("rate_limit") == "pagamentos-api"
    assert servico_do_cenario("nao_existe") is None


# --- Schema: 1 hipótese não vira erro --------------------------------------------------------


def test_uma_hipotese_valida_mas_o_modelo_continua_vendo_2_ou_3():
    analise = AnaliseIncidente.model_validate(UMA_HIPOTESE)
    assert len(analise.hipoteses) == 1
    esquema = AnaliseIncidente.model_json_schema()
    assert esquema["properties"]["hipoteses"]["minItems"] == 2


def test_investigador_com_uma_hipotese_nao_vira_erro():
    modelo = roteiro(chamada("buscar_logs", {}), json.dumps(UMA_HIPOTESE))
    resultado = montar_investigador(modelo, _ferramentas()).invoke(
        {"mensagem": "o que está errado no sistema?", "historico": []}
    )
    assert resultado.erro is None and len(resultado.analise.hipoteses) == 1


def test_correcao_do_json_traz_o_erro_de_validacao():
    modelo = roteiro(chamada("buscar_logs", {}), '{"severidade": "alta"}', json.dumps(UMA_HIPOTESE))
    montar_investigador(modelo, _ferramentas()).invoke({"mensagem": "x", "historico": []})
    pedido = str(modelo.chamadas[-1][-1].content)
    assert "ONLY the AnaliseIncidente JSON object" in pedido and "hipoteses" in pedido


# --- Investigador: sem ferramenta não conclui ------------------------------------------------


def test_resposta_sem_ferramenta_recebe_pedido_de_investigar():
    modelo = roteiro(
        json.dumps(SISTEMA_NORMAL),  # 1ª: conclui sem chamar nada
        chamada("buscar_logs", {}),  # depois do pedido: visão geral
        json.dumps(UMA_HIPOTESE),
    )
    resultado = montar_investigador(modelo, _ferramentas()).invoke(
        {"mensagem": "tem alguma coisa com problema?", "historico": []}
    )
    assert [passo.ferramenta for passo in resultado.trajetoria] == ["buscar_logs"]
    pedidos = [str(m.content) for lote in modelo.chamadas for m in lote]
    assert any("without calling any tool" in texto for texto in pedidos)


def test_sem_nenhuma_ferramenta_nao_afirma_ausencia_de_erro():
    modelo = roteiro(json.dumps(SISTEMA_NORMAL))  # nunca chama ferramenta
    resultado = montar_investigador(modelo, _ferramentas()).invoke(
        {"mensagem": "tem alguma coisa com problema?", "historico": []}
    )
    analise = resultado.analise
    assert resultado.trajetoria == []
    assert all(h.evidencia_insuficiente for h in analise.hipoteses)
    assert all(h.confianca <= 0.3 for h in analise.hipoteses)
    assert all(not h.evidencia for h in analise.hipoteses)
    assert analise.evidencia_insuficiente


def test_mensagem_sem_servico_recebe_o_servico_da_sessao():
    modelo = roteiro(chamada("buscar_logs", {}), json.dumps(UMA_HIPOTESE))
    montar_investigador(modelo, _ferramentas()).invoke(
        {
            "mensagem": "tem alguma coisa com problema?",
            "historico": [],
            "nlu": _nlu("pagamentos-api"),
        }
    )
    pergunta = str(modelo.chamadas[0][-1].content)
    assert pergunta.startswith("tem alguma coisa com problema?")
    assert "pagamentos-api" in pergunta


def test_prompt_tem_a_regra_da_visao_geral():
    texto = " ".join(SISTEMA_AGENTE.split())
    assert "names no service" in texto
    assert "without servico" in texto
    assert "never conclude that nothing is wrong" in texto.lower()


# --- Pipeline e conversa: o serviço da sessão --------------------------------------------------


def _moderar(texto):
    return ResultadoModeracao(status="ok")


def test_pipeline_herda_o_servico_da_sessao_e_nao_pede_servico():
    vistos = []

    def investigar(estado):
        vistos.append(estado["nlu"])
        return ResultadoInvestigacao(
            analise=AnaliseIncidente.model_validate(UMA_HIPOTESE), trajetoria=[]
        )

    pipe = montar_pipeline(
        None,
        _moderar,
        nlu=RunnableLambda(lambda e: _nlu(None, "qual serviço está com erro e desde quando")),
        investigacao=RunnableLambda(investigar),
    )
    resposta = pipe.invoke(
        {"mensagem": "tem alguma coisa com problema?", "historico": [], "servico_sessao": "x-api"}
    )
    assert resposta.rota == "investigacao"
    assert vistos[0].servico == "x-api" and vistos[0].dado_faltante is None


def test_sem_servico_na_sessao_o_pedido_legitimo_fica():
    pipe = montar_pipeline(
        None,
        _moderar,
        nlu=RunnableLambda(lambda e: _nlu(None, "qual serviço está com erro")),
        investigacao=RunnableLambda(
            lambda e: ResultadoInvestigacao(
                analise=AnaliseIncidente.model_validate(UMA_HIPOTESE), trajetoria=[]
            )
        ),
    )
    resposta = pipe.invoke({"mensagem": "tem alguma coisa com problema?", "historico": []})
    assert resposta.nlu.servico is None and resposta.nlu.dado_faltante


def test_conversa_repassa_o_servico_da_sessao():
    entradas = []

    def pipeline(entrada):
        entradas.append(entrada)
        from agente.schemas import RespostaFixa, RespostaTurno

        return RespostaTurno(
            rota="fixa",
            moderacao=ResultadoModeracao(status="ok"),
            fixa=RespostaFixa(texto="ok", camada=2, categoria="saudacao"),
        )

    conversa = montar_conversa(RunnableLambda(pipeline), roteiro("resumo"))
    sessao = abrir_sessao("pool_esgotado", servico="pedidos-api")
    conversa.turno(sessao, "tem alguma coisa com problema?")
    assert entradas[0]["servico_sessao"] == "pedidos-api"


def test_sessao_do_agente_integrado_nasce_com_o_servico_do_cenario(tmp_path):
    from langchain_core.embeddings import DeterministicFakeEmbedding

    from agente.integrado import AgenteIntegrado
    from agente.memoria import MemoriaLongoPrazo

    embeddings = DeterministicFakeEmbedding(size=8)
    agente = AgenteIntegrado(
        roteiro("ok"),
        embeddings=embeddings,
        indice=object(),
        memoria=MemoriaLongoPrazo(embeddings, tmp_path / "m.json"),
        auditor=False,
        avaliar_relevancia=False,
    )
    assert agente.abrir_sessao("rate_limit").servico == "pagamentos-api"
    assert agente.abrir_sessao("pool_esgotado").servico == "pedidos-api"
