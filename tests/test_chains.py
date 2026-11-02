"""Testes das composições da US2: sequencial, paralela, roteador moderno e clássico."""

import time

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda

from agente.chains import (
    montar_chain_paralela,
    montar_chain_sequencial,
    montar_roteador_moderno,
    montar_router_chain_classica,
)
from agente.schemas import AnaliseNLU

ERRO = "java.lang.OutOfMemoryError: heap\n  at com.loja.Pedido.salvar(Pedido.java:10)\n"


def test_sequencial_devolve_tres_etapas_em_ordem():
    llm = FakeListChatModel(responses=["Causa provável: heap cheio.", "Resumo: aumentar o heap."])
    saida = montar_chain_sequencial(llm).invoke({"texto": ERRO})
    assert list(saida)[:4] == ["texto", "preprocessado", "analise", "resumo"]
    assert "OutOfMemoryError" in saida["preprocessado"]
    assert saida["analise"] == "Causa provável: heap cheio."
    assert saida["resumo"] == "Resumo: aumentar o heap."


class FonteLenta:
    """Fonte falsa: cada consulta dorme 0,3 s."""

    def _dorme(self, valor):
        time.sleep(0.3)
        return valor

    def tags_do_servico(self):
        return []

    def logs(self, servico, nivel=None):
        return self._dorme(
            {
                "total": 1,
                "truncado": False,
                "logs": [
                    {
                        "horario": "2026-01-01T10:00:00",
                        "servico": servico,
                        "nivel": "ERROR",
                        "mensagem": "falha",
                    }
                ],
            }
        )

    def metricas(self, servico, metrica=None):
        return self._dorme(
            [
                {
                    "servico": servico,
                    "metrica": "cpu",
                    "unidade": "%",
                    "resumo": {"min": 10.0, "max": 90.0, "media": 50.0, "ultimo": 90.0},
                }
            ]
        )

    def deploys(self, servico=None):
        return self._dorme([])


def test_paralela_devolve_dicionario_e_roda_em_paralelo():
    chain = montar_chain_paralela(FonteLenta())
    inicio = time.perf_counter()
    saida = chain.invoke({"servico": "pedidos-api"})
    assert time.perf_counter() - inicio < 0.6
    assert set(saida) == {"logs", "metricas", "deploys"}
    assert "falha" in saida["logs"] and "cpu" in saida["metricas"]
    assert saida["deploys"] == "No deploys found."


def test_roteador_moderno_leva_cada_intencao_ao_destino():
    destinos = {
        "checar_deploy": RunnableLambda(lambda estado: "deploy"),
        "checar_metrica": RunnableLambda(lambda estado: "metrica"),
    }
    rota = montar_roteador_moderno(destinos, RunnableLambda(lambda estado: "padrao"))

    def para(intencao):
        return rota.invoke({"nlu": AnaliseNLU(intencao=intencao)})

    assert para("checar_deploy") == "deploy"
    assert para("checar_metrica") == "metrica"
    assert para("saudacao") == "padrao"


def test_router_chain_classica_roteia_com_modelo_falso():
    roteador = '```json\n{"destination": "infraestrutura", "next_inputs": "pod morreu"}\n```'
    llm = FakeListChatModel(responses=[roteador, "Verifique o limite de memória do pod."])
    chain = montar_router_chain_classica(llm)
    assert set(chain.destination_chains) == {
        "erro_de_codigo",
        "dependencia_externa",
        "infraestrutura",
    }
    saida = chain.invoke({"input": "pod morreu"})
    assert saida["text"] == "Verifique o limite de memória do pod."
