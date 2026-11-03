"""Os prompts de sistema ficam em inglês e terminam pedindo resposta em português."""

from agente.agente_react import PEDIDO_JSON, SISTEMA_AGENTE, SISTEMA_REGISTRO
from agente.chains import _DESTINOS_CLASSICOS, prompt_analise, prompt_resumo
from agente.classico import FORMATO_CLASSICO
from agente.prompts import (
    SISTEMA_AVALIACAO,
    SISTEMA_INVESTIGACAO,
    SISTEMA_NLU,
    SISTEMA_RESOLUCAO,
    respostas_fixas,
)

FECHO = "Always answer in Brazilian Portuguese."


def test_cada_prompt_de_sistema_termina_pedindo_portugues():
    textos = [SISTEMA_NLU, SISTEMA_INVESTIGACAO, SISTEMA_AGENTE.rstrip(), FORMATO_CLASSICO]
    textos += [PEDIDO_JSON, prompt_analise.messages[0].prompt.template]
    textos += [SISTEMA_RESOLUCAO, SISTEMA_AVALIACAO, SISTEMA_REGISTRO.rstrip()]
    textos += [prompt_resumo.messages[0].prompt.template]
    for texto in textos:
        assert texto.rstrip().endswith(FECHO)


def test_prompts_dos_destinos_classicos_pedem_portugues():
    for destino in _DESTINOS_CLASSICOS:
        assert FECHO in destino["prompt_template"]


def test_respostas_fixas_seguem_em_portugues():
    for chave, modelo in respostas_fixas.items():
        texto = modelo.format()
        assert FECHO not in texto, chave
        assert any(letra in texto for letra in "ãçõéáíê") or "Olá" in texto or "só" in texto
