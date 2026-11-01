import pytest
from pydantic import ValidationError

from agente.schemas import AnaliseIncidente, AnaliseNLU, Hipotese


def _hip(causa="a", confianca=0.5, **kw):
    return Hipotese(causa=causa, confianca=confianca, evidencia="trecho", **kw)


def _tres(**kw):
    if kw.get("evidencia_insuficiente"):
        kw.setdefault("dado_que_falta", "log do pool")
    return [_hip("a", 0.2, **kw), _hip("b", 0.9, **kw), _hip("c", 0.5, **kw)]


def _analise(**kw):
    base = dict(severidade="alta", categoria="null_pointer", servico="pagamentos-api",
                resumo="r", hipoteses=_tres(), proximos_passos=["ver logs"])
    base.update(kw)
    return AnaliseIncidente(**base)


def test_nlu_rejeita_intencao_invalida():
    with pytest.raises(ValidationError):
        AnaliseNLU(intencao="dancar")


def test_nlu_aceita_intencao_valida():
    assert AnaliseNLU(intencao="investigar_erro").servico is None


def test_hipotese_rejeita_evidencia_vazia():
    with pytest.raises(ValidationError):
        Hipotese(causa="x", confianca=0.5, evidencia="  ")


@pytest.mark.parametrize("c", [-0.1, 1.1])
def test_hipotese_rejeita_confianca_fora_da_faixa(c):
    with pytest.raises(ValidationError):
        Hipotese(causa="x", confianca=c, evidencia="trecho")


def test_analise_exige_proximos_passos():
    with pytest.raises(ValidationError):
        _analise(proximos_passos=[])


@pytest.mark.parametrize("n", [0, 1, 4])
def test_analise_rejeita_menos_de_duas_ou_mais_de_tres_hipoteses(n):
    hs = [_hip(str(i), 0.1 * (i + 1)) for i in range(n)]
    with pytest.raises(ValidationError):
        _analise(hipoteses=hs)


@pytest.mark.parametrize("n", [2, 3])
def test_analise_aceita_duas_ou_tres_hipoteses(n):
    hs = [_hip(str(i), 0.1 * (i + 1)) for i in range(n)]
    assert len(_analise(hipoteses=hs).hipoteses) == n


def test_hipoteses_ordenadas_por_confianca():
    assert [x.causa for x in _analise().hipoteses] == ["b", "c", "a"]


def test_evidencia_insuficiente_por_hipotese_default_falso():
    assert _hip().evidencia_insuficiente is False


def test_evidencia_insuficiente_da_analise_so_se_todas_marcadas():
    assert _analise().evidencia_insuficiente is False
    hs = _tres()
    hs[0] = _hip("a", 0.2, evidencia_insuficiente=True, dado_que_falta="métrica do pool")
    assert _analise(hipoteses=hs).evidencia_insuficiente is False
    assert _analise(hipoteses=_tres(evidencia_insuficiente=True)).evidencia_insuficiente is True


def test_evidencia_insuficiente_fora_do_schema_de_validacao():
    assert "evidencia_insuficiente" not in AnaliseIncidente.model_json_schema()["properties"]


# Saída real do modelo (execução com a OpenAI): a 3ª hipótese veio com
# evidencia_insuficiente=true e SEM o campo "evidencia", o que quebrava a validação.
JSON_REAL_SEM_EVIDENCIA = {
    "severidade": "alta", "categoria": "dependencia_externa", "servico": "pagamentos-api",
    "resumo": "Timeouts ao chamar o gateway PagaFácil, que está com falha geral.",
    "hipoteses": [
        {"causa": "Gateway de pagamento PagaFácil fora do ar", "confianca": 0.9,
         "evidencia": "A status page da PagaFácil mostra 'Major outage' desde 09:05",
         "evidencia_insuficiente": False},
        {"causa": "Timeout de leitura curto demais no cliente HTTP", "confianca": 0.3,
         "evidencia": "java.net.SocketTimeoutException: Read timed out",
         "evidencia_insuficiente": False},
        {"causa": "Possível aumento de carga no pagamentos-api", "confianca": 0.1,
         "evidencia_insuficiente": True, "dado_que_falta": "taxa de requisições por minuto"},
    ],
    "proximos_passos": ["Acompanhar a status page da PagaFácil"],
}


def test_hipotese_insuficiente_sem_evidencia_e_aceita_com_dado_que_falta():
    a = AnaliseIncidente.model_validate(JSON_REAL_SEM_EVIDENCIA)
    h = a.hipoteses[-1]
    assert h.evidencia is None and h.dado_que_falta == "taxa de requisições por minuto"


def test_hipotese_insuficiente_exige_dado_que_falta():
    with pytest.raises(ValidationError):
        Hipotese(causa="x", confianca=0.1, evidencia_insuficiente=True)


def test_hipotese_suficiente_exige_evidencia():
    with pytest.raises(ValidationError):
        Hipotese(causa="x", confianca=0.5)
