"""Travas determinísticas de qualidade da resposta: dado faltante indevido e ação que só repete
uma consulta que as ferramentas já fizeram."""

from agente.qualidade import (
    acao_de_consulta,
    dado_faltante_valido,
    repete_consulta,
    sanear_analise,
    sanear_nlu,
)
from agente.schemas import AcaoSugerida, AnaliseIncidente, AnaliseNLU, Hipotese

PERGUNTA = "O pagamentos-api está com erros desde as 14h. Qual a causa provável?"
FERRAMENTAS = {"buscar_logs", "buscar_metricas", "listar_deploys", "consultar_wiki", "sugerir_acao"}


def test_dado_faltante_que_e_a_propria_causa_e_descartado():
    assert not dado_faltante_valido("causa provável dos erros", PERGUNTA)
    assert not dado_faltante_valido("o motivo dos erros 500", PERGUNTA)
    assert not dado_faltante_valido("raiz do problema", PERGUNTA)


def test_dado_faltante_que_as_ferramentas_alcancam_e_descartado():
    assert not dado_faltante_valido("logs do pagamentos-api no período", PERGUNTA)
    assert not dado_faltante_valido("métricas de requisições", PERGUNTA)
    assert not dado_faltante_valido("deploys recentes", PERGUNTA)
    assert not dado_faltante_valido("análise do volume de requisições", PERGUNTA)


def test_dado_faltante_que_repete_a_pergunta_e_descartado():
    pergunta = "Qual a categoria mais comum dos incidentes do pedidos-api?"
    assert not dado_faltante_valido("categoria mais comum dos incidentes", pergunta)


def test_dado_faltante_que_so_o_engenheiro_sabe_fica():
    assert dado_faltante_valido("nome do serviço afetado", "está tudo dando erro")
    assert dado_faltante_valido("horário em que o erro começou", "o checkout quebrou")
    assert dado_faltante_valido("limite contratado com o provedor de SMS", PERGUNTA)


def test_sanear_nlu_remove_so_o_dado_indevido():
    nlu = AnaliseNLU(
        intencao="investigar_erro",
        servico="pagamentos-api",
        dado_faltante="causa provável dos erros",
    )
    limpo = sanear_nlu(nlu, PERGUNTA)
    assert limpo.dado_faltante is None and limpo.servico == "pagamentos-api"
    bom = AnaliseNLU(intencao="investigar_erro", dado_faltante="nome do serviço afetado")
    assert sanear_nlu(bom, "deu erro").dado_faltante == "nome do serviço afetado"
    assert sanear_nlu(None, PERGUNTA) is None


def test_acao_de_consulta_reconhece_verificar_e_consultar():
    assert acao_de_consulta("Verifique os logs para identificar o volume de requisições")
    assert acao_de_consulta("Consulte o limite documentado do plano contratado com o PagaFácil")
    assert acao_de_consulta("Checar as métricas de CPU")
    assert acao_de_consulta("Analisar os deploys recentes")
    assert not acao_de_consulta("Respeitar o Retry-After de 30 s com backoff exponencial")
    assert not acao_de_consulta("Limitar as chamadas ao PagaFácil a menos de 100 por minuto")
    assert not acao_de_consulta("Reverter o deploy v3.2.1")


def test_repete_consulta_so_quando_a_ferramenta_ja_rodou():
    assert repete_consulta("Verifique os logs do pagamentos-api", FERRAMENTAS)
    assert repete_consulta("Consulte o limite documentado do PagaFácil", FERRAMENTAS)
    assert not repete_consulta(
        "Conferir o diff da v3.2.1", FERRAMENTAS
    )  # comparar_versoes não rodou
    assert repete_consulta("Conferir o diff da v3.2.1", FERRAMENTAS | {"comparar_versoes"})
    assert not repete_consulta("Enfileirar os pagamentos no modo degradado", FERRAMENTAS)


def _analise(passos, acoes):
    return AnaliseIncidente(
        severidade="alta",
        categoria="dependencia_externa",
        resumo="429 do PagaFácil.",
        hipoteses=[
            Hipotese(causa="limite de 100/min excedido", confianca=0.9, evidencia="x150"),
            Hipotese(causa="falha no provedor", confianca=0.1, evidencia="sem 503"),
        ],
        proximos_passos=passos,
        acoes_sugeridas=acoes,
    )


def test_sanear_analise_tira_passos_e_acoes_que_repetem_consulta():
    acoes = [
        AcaoSugerida(acao="Verifique os logs para identificar o volume", motivo="m", risco="baixo"),
        AcaoSugerida(acao="Respeitar o Retry-After de 30 s", motivo="m", risco="baixo"),
    ]
    analise = _analise(
        [
            "Verifique os logs para identificar o volume de requisições.",
            "Ativar o modo degradado para enfileirar pagamentos.",
        ],
        acoes,
    )
    limpa = sanear_analise(analise, FERRAMENTAS)
    assert limpa.proximos_passos == ["Ativar o modo degradado para enfileirar pagamentos."]
    assert [a.acao for a in limpa.acoes_sugeridas] == ["Respeitar o Retry-After de 30 s"]


def test_sanear_analise_sem_passo_util_usa_as_acoes_sugeridas():
    acoes = [AcaoSugerida(acao="Respeitar o Retry-After de 30 s", motivo="m", risco="baixo")]
    analise = _analise(["Verifique os logs.", "Consulte a wiki do PagaFácil."], acoes)
    limpa = sanear_analise(analise, FERRAMENTAS)
    assert limpa.proximos_passos == [
        "Avaliar e aprovar a ação sugerida: Respeitar o Retry-After de 30 s"
    ]


def test_sanear_analise_sem_nada_util_parte_da_causa_principal():
    analise = _analise(["Verifique os logs."], [])
    passos = sanear_analise(analise, FERRAMENTAS).proximos_passos
    assert passos == ["Corrigir a causa principal: limite de 100/min excedido"]
