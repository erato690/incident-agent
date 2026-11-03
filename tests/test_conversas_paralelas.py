"""rodar_conversas_paralelas: ordem original e dependência (sem chave, com fakes)."""

import threading
import time

from agente.bateria import rodar_conversas_paralelas


class GrafoFalso:
    """Grava a ordem de início/fim dos turnos; o `turno` devolve a própria mensagem."""

    def __init__(self, eventos, pausa=0.0):
        self.eventos, self.pausa = eventos, pausa

    def turno(self, sessao, mensagem):
        self.eventos.append(("inicio", mensagem, threading.get_ident()))
        time.sleep(self.pausa)
        self.eventos.append(("fim", mensagem, threading.get_ident()))
        return mensagem


def _fabrica(eventos, pausa=0.0):
    grafo = GrafoFalso(eventos, pausa)
    return lambda cenario: grafo


def _conversa(id_, depende_de=None):
    conversa = {
        "id": id_,
        "cenario": "c",
        "turnos": [{"mensagem": f"{id_}1"}, {"mensagem": f"{id_}2"}],
    }
    return {**conversa, "depende_de": depende_de} if depende_de else conversa


def test_resultados_na_ordem_original_mesmo_com_tempos_diferentes():
    eventos: list = []
    conversas = [_conversa("a"), _conversa("b"), _conversa("c")]
    resultados = rodar_conversas_paralelas(_fabrica(eventos, 0.01), conversas)
    assert resultados == [["a1", "a2"], ["b1", "b2"], ["c1", "c2"]]


def test_independentes_rodam_ao_mesmo_tempo():
    eventos: list = []
    rodar_conversas_paralelas(_fabrica(eventos, 0.05), [_conversa("a"), _conversa("b")])
    inicios = [i for i, e in enumerate(eventos) if e[0] == "inicio"]
    fins = [i for i, e in enumerate(eventos) if e[0] == "fim"]
    assert inicios[1] < fins[0]


def test_dependente_roda_depois_da_dependencia_na_mesma_linha():
    eventos: list = []
    conversas = [_conversa("b", depende_de="a"), _conversa("a"), _conversa("c")]
    resultados = rodar_conversas_paralelas(_fabrica(eventos, 0.01), conversas)
    assert resultados == [["b1", "b2"], ["a1", "a2"], ["c1", "c2"]]
    ordem = [e[1] for e in eventos if e[0] == "fim" and e[1][0] in "ab"]
    assert ordem.index("a2") < ordem.index("b1")
    linhas = {e[1][0]: e[2] for e in eventos}
    assert linhas["a"] == linhas["b"]


def test_dependencia_fora_da_lista_e_ignorada():
    resultados = rodar_conversas_paralelas(_fabrica([]), [_conversa("b", depende_de="zzz")])
    assert resultados == [["b1", "b2"]]
