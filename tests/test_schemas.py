from datetime import datetime

import pytest
from pydantic import ValidationError

from agente.schemas import (
    AcaoSugerida,
    AnaliseIncidente,
    AnaliseNLU,
    ContextoTurno,
    FatoSemantico,
    Hipotese,
    ListaAcoes,
    PassoTrajetoria,
    RespostaTurno,
    ResultadoInvestigacao,
    ResultadoModeracao,
)


def _hip(causa="a", confianca=0.5, **opcoes):
    return Hipotese(causa=causa, confianca=confianca, evidencia="trecho", **opcoes)


def _tres(**opcoes):
    if opcoes.get("evidencia_insuficiente"):
        opcoes.setdefault("dado_que_falta", "log do pool")
    return [_hip("a", 0.2, **opcoes), _hip("b", 0.9, **opcoes), _hip("c", 0.5, **opcoes)]


def _analise(**opcoes):
    base = dict(
        severidade="alta",
        categoria="null_pointer",
        servico="pagamentos-api",
        resumo="r",
        hipoteses=_tres(),
        proximos_passos=["ver logs"],
    )
    base.update(opcoes)
    return AnaliseIncidente(**base)


def test_nlu_rejeita_intencao_invalida():
    with pytest.raises(ValidationError):
        AnaliseNLU(intencao="dancar")


def test_nlu_aceita_intencao_valida():
    assert AnaliseNLU(intencao="investigar_erro").servico is None


def test_hipotese_rejeita_evidencia_vazia():
    with pytest.raises(ValidationError):
        Hipotese(causa="x", confianca=0.5, evidencia="  ")


@pytest.mark.parametrize("confianca", [-0.1, 1.1])
def test_hipotese_rejeita_confianca_fora_da_faixa(confianca):
    with pytest.raises(ValidationError):
        Hipotese(causa="x", confianca=confianca, evidencia="trecho")


def test_analise_exige_proximos_passos():
    with pytest.raises(ValidationError):
        _analise(proximos_passos=[])


@pytest.mark.parametrize("quantidade", [0, 1, 4])
def test_analise_rejeita_menos_de_duas_ou_mais_de_tres_hipoteses(quantidade):
    hipoteses = [_hip(str(indice), 0.1 * (indice + 1)) for indice in range(quantidade)]
    with pytest.raises(ValidationError):
        _analise(hipoteses=hipoteses)


@pytest.mark.parametrize("quantidade", [2, 3])
def test_analise_aceita_duas_ou_tres_hipoteses(quantidade):
    hipoteses = [_hip(str(indice), 0.1 * (indice + 1)) for indice in range(quantidade)]
    assert len(_analise(hipoteses=hipoteses).hipoteses) == quantidade


def test_hipoteses_ordenadas_por_confianca():
    assert [hipotese.causa for hipotese in _analise().hipoteses] == ["b", "c", "a"]


def test_evidencia_insuficiente_por_hipotese_default_falso():
    assert _hip().evidencia_insuficiente is False


def test_evidencia_insuficiente_da_analise_so_se_todas_marcadas():
    assert _analise().evidencia_insuficiente is False
    hipoteses = _tres()
    hipoteses[0] = _hip("a", 0.2, evidencia_insuficiente=True, dado_que_falta="métrica do pool")
    assert _analise(hipoteses=hipoteses).evidencia_insuficiente is False
    assert _analise(hipoteses=_tres(evidencia_insuficiente=True)).evidencia_insuficiente is True


def test_evidencia_insuficiente_fora_do_schema_de_validacao():
    assert "evidencia_insuficiente" not in AnaliseIncidente.model_json_schema()["properties"]


# Saída real do modelo (execução com a OpenAI): a 3ª hipótese veio com
# evidencia_insuficiente=true e SEM o campo "evidencia", o que quebrava a validação.
JSON_REAL_SEM_EVIDENCIA = {
    "severidade": "alta",
    "categoria": "dependencia_externa",
    "servico": "pagamentos-api",
    "resumo": "Timeouts ao chamar o gateway PagaFácil, que está com falha geral.",
    "hipoteses": [
        {
            "causa": "Gateway de pagamento PagaFácil fora do ar",
            "confianca": 0.9,
            "evidencia": "A status page da PagaFácil mostra 'Major outage' desde 09:05",
            "evidencia_insuficiente": False,
        },
        {
            "causa": "Timeout de leitura curto demais no cliente HTTP",
            "confianca": 0.3,
            "evidencia": "java.net.SocketTimeoutException: Read timed out",
            "evidencia_insuficiente": False,
        },
        {
            "causa": "Possível aumento de carga no pagamentos-api",
            "confianca": 0.1,
            "evidencia_insuficiente": True,
            "dado_que_falta": "taxa de requisições por minuto",
        },
    ],
    "proximos_passos": ["Acompanhar a status page da PagaFácil"],
}


def test_hipotese_insuficiente_sem_evidencia_e_aceita_com_dado_que_falta():
    analise = AnaliseIncidente.model_validate(JSON_REAL_SEM_EVIDENCIA)
    hipotese = analise.hipoteses[-1]
    assert (
        hipotese.evidencia is None and hipotese.dado_que_falta == "taxa de requisições por minuto"
    )


def test_hipotese_insuficiente_exige_dado_que_falta():
    with pytest.raises(ValidationError):
        Hipotese(causa="x", confianca=0.1, evidencia_insuficiente=True)


def test_hipotese_suficiente_exige_evidencia():
    with pytest.raises(ValidationError):
        Hipotese(causa="x", confianca=0.5)


# ---- Trajetória e resultado da investigação com agente ----


def _passo(**opcoes):
    base = dict(ferramenta="buscar_logs", argumentos={"servico": "x"}, duracao_ms=3, tamanho=10)
    base.update(opcoes)
    return PassoTrajetoria(**base)


def test_passo_trajetoria_padroes():
    passo = _passo()
    assert passo.erro is None and passo.reserva is False


def test_passo_rejeita_duracao_negativa():
    with pytest.raises(ValidationError):
        _passo(duracao_ms=-1)


def test_resultado_exige_exatamente_um_entre_analise_e_erro():
    with pytest.raises(ValidationError):
        ResultadoInvestigacao()
    with pytest.raises(ValidationError):
        ResultadoInvestigacao(analise=_analise(), erro="falhou")
    assert ResultadoInvestigacao(erro="falhou").trajetoria == []
    assert ResultadoInvestigacao(analise=_analise(), trajetoria=[_passo()]).erro is None


def test_resposta_turno_trajetoria_default_vazio():
    resposta = RespostaTurno(rota="erro", moderacao=ResultadoModeracao(status="ok"), erro="x")
    assert resposta.trajetoria == []


def test_acao_sugerida_status_fixo():
    acao = AcaoSugerida(acao="reagendar", motivo="m", risco="baixo")
    assert acao.status == "sugerida (não executada)" and acao.runbook is None
    with pytest.raises(ValidationError):
        AcaoSugerida(acao="a", motivo="m", risco="baixo", status="executada")
    with pytest.raises(ValidationError):
        AcaoSugerida(acao="a", motivo="m", risco="extremo")


def test_lista_acoes_de_um_a_tres():
    item = {"acao": "a", "motivo": "m", "risco": "alto"}
    assert len(ListaAcoes(acoes=[item] * 3).acoes) == 3
    for quantidade in (0, 4):
        with pytest.raises(ValidationError):
            ListaAcoes(acoes=[item] * quantidade)


def test_acoes_sugeridas_fora_do_schema_do_modelo_mas_no_dump():
    from langchain_core.output_parsers import JsonOutputParser

    instrucoes = JsonOutputParser(pydantic_object=AnaliseIncidente).get_format_instructions()
    assert "acoes_sugeridas" not in instrucoes
    analise = _analise()
    assert analise.acoes_sugeridas == []
    assert analise.model_dump()["acoes_sugeridas"] == []


def test_intencao_confirmar_fato_e_campos_novos():
    assert AnaliseNLU(intencao="confirmar_fato").intencao == "confirmar_fato"
    fato = FatoSemantico(
        assunto="PagaFácil", fato="100 req/min", fonte="usuario", verificado_em=datetime.now()
    )
    contexto = ContextoTurno()
    assert contexto.acoes_sugeridas == [] and contexto.fato_gravado is None
    resposta = RespostaTurno(rota="memoria", moderacao={"status": "ok"}, fato=fato)
    assert resposta.fato == fato
    assert RespostaTurno(rota="fixa", moderacao={"status": "ok"}).fato is None
