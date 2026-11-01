import pytest
from pydantic import ValidationError

from agente.schemas import AnaliseIncidente, AnaliseNLU, Hipotese


def _analise(**kw):
    base = dict(severidade="alta", categoria="null_pointer", servico="pagamentos-api",
                resumo="r", hipoteses=[], evidencia_insuficiente=True,
                proximos_passos=["ver logs"])
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


def test_hipoteses_vazias_exigem_evidencia_insuficiente():
    with pytest.raises(ValidationError):
        _analise(hipoteses=[], evidencia_insuficiente=False)
    assert _analise().hipoteses == []


def test_hipoteses_ordenadas_por_confianca():
    h = [Hipotese(causa="a", confianca=0.2, evidencia="e"),
         Hipotese(causa="b", confianca=0.9, evidencia="e")]
    a = _analise(hipoteses=h, evidencia_insuficiente=False)
    assert [x.causa for x in a.hipoteses] == ["b", "a"]
