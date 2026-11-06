"""Fase 4 no pipeline: confirmar_fato vai ao Registrador de fato; ações vão para a análise."""

from datetime import datetime, timedelta

from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.runnables import RunnableLambda

from agente.agente_react import SISTEMA_REGISTRO_FATO, montar_registrador
from agente.ferramentas import CHAVE_CONTEXTO, montar_ferramentas_fato
from agente.memoria import MemoriaLongoPrazo
from agente.pipeline import montar_pipeline
from agente.prompts import SISTEMA_NLU
from agente.schemas import (
    AcaoSugerida,
    AnaliseNLU,
    ContextoTurno,
    ResultadoInvestigacao,
    ResultadoModeracao,
)
from tests.fakes import chamada, roteiro
from tests.test_roteamento import ANALISE

AGORA = datetime(2026, 11, 5, 12, 0)
MENSAGEM = "Confirmado: o limite do PagaFácil é 100 requisições por minuto"
FECHO = "Always answer in Brazilian Portuguese."


def _nlu(intencao="confirmar_fato", servico=None):
    return RunnableLambda(lambda estado: AnaliseNLU(intencao=intencao, servico=servico))


def _memoria():
    return MemoriaLongoPrazo(DeterministicFakeEmbedding(size=64), agora=lambda: AGORA)


def _gravacao(assunto="PagaFácil", fato="O limite é 100 requisições por minuto"):
    return chamada("gravar_fato", {"assunto": assunto, "fato": fato})


def _pipe(memoria, modelo=None, nlu=None, investigacao=None, registro_fato=True):
    registro = None
    if registro_fato:
        modelo = modelo or roteiro(_gravacao(), "Registrei.")
        registro = montar_registrador(
            modelo, montar_ferramentas_fato(memoria), system_prompt=SISTEMA_REGISTRO_FATO
        )
    return montar_pipeline(
        None,
        lambda texto: ResultadoModeracao(status="ok"),
        nlu=nlu or _nlu(),
        investigacao=investigacao or RunnableLambda(lambda estado: ANALISE),
        memoria=memoria,
        registro=RunnableLambda(lambda estado: "não usado"),
        registro_fato=registro,
    )


def test_prompt_nlu_reconhece_confirmar_fato_distinto_de_confirmar_causa():
    assert "confirmar_fato" in SISTEMA_NLU and "confirmar_causa" in SISTEMA_NLU
    assert "limite" in SISTEMA_NLU and SISTEMA_NLU.rstrip().endswith(FECHO)


def test_sistema_do_registrador_de_fato_em_ingles():
    assert "gravar_fato" in SISTEMA_REGISTRO_FATO and "exactly once" in SISTEMA_REGISTRO_FATO
    assert SISTEMA_REGISTRO_FATO.rstrip().endswith(FECHO)


def test_confirmar_fato_grava_na_wiki_e_responde_rota_memoria():
    memoria = _memoria()
    resposta = _pipe(memoria).invoke({"mensagem": MENSAGEM})  # sem incidente nem sessão
    assert resposta.rota == "memoria" and resposta.episodio is None
    assert resposta.fato.assunto == "PagaFácil" and resposta.fato.fonte == "usuario"
    validade = (AGORA + timedelta(days=90)).strftime("%Y-%m-%d")
    assert resposta.fixa.texto == (
        "Fato registrado na wiki: PagaFácil: O limite é 100 requisições por minuto "
        f"(fonte: usuário, válido até {validade})."
    )
    assert [p.ferramenta for p in resposta.trajetoria] == ["gravar_fato"]
    assert memoria.consultar_fatos_semanticos("pagafácil", "limite")


def test_sem_gravar_vira_rota_erro_legivel():
    memoria = _memoria()
    resposta = _pipe(memoria, modelo=roteiro("Pronto, registrei.")).invoke({"mensagem": MENSAGEM})
    assert resposta.rota == "erro" and resposta.fato is None
    assert "nada foi registrado" in resposta.erro and "gravar_fato" in resposta.erro
    assert memoria.consultar_fatos_semanticos("PagaFácil", "limite") == []


def test_falha_do_registrador_vira_rota_erro():
    def quebra(estado):
        raise RuntimeError("modelo fora do ar")

    pipe = montar_pipeline(
        None,
        lambda t: ResultadoModeracao(status="ok"),
        nlu=_nlu(),
        investigacao=RunnableLambda(str),
        memoria=_memoria(),
        registro=RunnableLambda(lambda estado: "não usado"),
        registro_fato=RunnableLambda(quebra),
    )
    saida = pipe.invoke({"mensagem": MENSAGEM})
    assert saida.rota == "erro" and "modelo fora do ar" in saida.erro


def test_segredo_na_mensagem_nao_chega_ao_modelo():
    modelo = roteiro(_gravacao(), "ok")
    _pipe(_memoria(), modelo=modelo).invoke({"mensagem": MENSAGEM + " token=abc123"})
    assert all("abc123" not in str(msg.content) for msg in modelo.chamadas[0])


def test_gravar_fato_fora_da_confirmacao_e_recusado():
    memoria = _memoria()
    ferramentas = montar_ferramentas_fato(memoria)
    contexto = ContextoTurno(intencao="investigar_erro")
    saida = ferramentas[0].invoke(
        {"assunto": "X", "fato": "y"}, {"configurable": {CHAVE_CONTEXTO: contexto}}
    )
    assert "nada foi gravado" in saida and contexto.fato_gravado is None


def test_sem_memoria_confirmar_fato_e_resposta_fixa():
    pipe = montar_pipeline(
        None,
        lambda t: ResultadoModeracao(status="ok"),
        nlu=_nlu(),
        investigacao=RunnableLambda(str),
    )
    resposta = pipe.invoke({"mensagem": MENSAGEM})
    assert resposta.rota == "fixa" and resposta.fixa.categoria == "confirmar_fato"
    assert resposta.fixa.texto == "Para guardar fatos preciso da memória de longo prazo ligada."


def test_confirmar_causa_sem_memoria_nao_mudou():
    pipe = montar_pipeline(
        None,
        lambda t: ResultadoModeracao(status="ok"),
        nlu=_nlu("confirmar_causa"),
        investigacao=RunnableLambda(str),
    )
    assert pipe.invoke({"mensagem": "confirmado: deploy"}).fixa.categoria == "confirmar_causa"


# --- ações sugeridas copiadas do contexto para a análise -------------------------------------

ACAO = AcaoSugerida(acao="Aguardar o fim do REINDEX", motivo="bloqueia a tabela", risco="baixo")


def _investigacao_que_sugere(com_resultado=False):
    def investiga(estado, config):
        contexto = config["configurable"][CHAVE_CONTEXTO]
        contexto.acoes_sugeridas = [ACAO]
        if com_resultado:
            return ResultadoInvestigacao(analise=ANALISE, trajetoria=[])
        return ANALISE

    return RunnableLambda(investiga)


def test_acoes_do_contexto_vao_para_a_analise_com_memoria():
    pipe = _pipe(_memoria(), nlu=_nlu("investigar_erro"), investigacao=_investigacao_que_sugere())
    resposta = pipe.invoke({"mensagem": "pedidos lentos"})
    assert resposta.rota == "investigacao" and resposta.analise.acoes_sugeridas == [ACAO]
    assert resposta.analise.acoes_sugeridas[0].status == "sugerida (não executada)"


def test_acoes_do_contexto_vao_para_a_analise_sem_memoria():
    pipe = montar_pipeline(
        None,
        lambda t: ResultadoModeracao(status="ok"),
        nlu=_nlu("investigar_erro"),
        investigacao=_investigacao_que_sugere(com_resultado=True),
    )
    resposta = pipe.invoke({"mensagem": "pedidos lentos"})
    assert resposta.analise.acoes_sugeridas == [ACAO]


def test_sem_sugerir_acao_a_analise_fica_igual():
    pipe = montar_pipeline(
        None,
        lambda t: ResultadoModeracao(status="ok"),
        nlu=_nlu("investigar_erro"),
        investigacao=RunnableLambda(lambda estado: ANALISE),
    )
    resposta = pipe.invoke({"mensagem": "pedidos lentos"})
    assert resposta.analise == ANALISE and resposta.analise.acoes_sugeridas == []


def test_citar_fatos_poe_fonte_e_data_na_hipotese_com_mais_palavras_em_comum():
    from datetime import datetime

    from agente.pipeline import citar_fatos
    from agente.schemas import AnaliseIncidente, FatoSemantico

    analise = AnaliseIncidente(
        severidade="alta",
        categoria="dependencia_externa",
        servico="pagamentos-api",
        resumo="r",
        hipoteses=[
            {
                "causa": "tráfego estourou o limite de requisições do PagaFácil",
                "confianca": 0.8,
                "evidencia": "buscar_logs: 429",
            },
            {"causa": "deploy recente", "confianca": 0.1, "evidencia": "listar_deploys: nenhum"},
        ],
        proximos_passos=["x"],
    )
    fato = FatoSemantico(
        assunto="PagaFácil",
        fato="A API do PagaFácil aceita 100 requisições por minuto por conta.",
        fonte="documentacao",
        verificado_em=datetime(2026, 11, 5, 12, 0),
    )
    citada = citar_fatos(analise, [fato, fato])
    evidencia = citada.hipoteses[0].evidencia
    assert evidencia.count("consultar_wiki: PagaFácil:") == 1
    assert "(fonte documentacao, verificado em 2026-11-05)" in evidencia
    assert "consultar_wiki" not in (citada.hipoteses[1].evidencia or "")


def test_prompt_nlu_separa_resumo_da_conversa_do_post_mortem():
    texto = " ".join(SISTEMA_NLU.split())
    assert '"resume o que sabemos até aqui" -> investigar_erro' in texto
    assert "dado_faltante is only for information that ONLY the engineer knows" in texto
