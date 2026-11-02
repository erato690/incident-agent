"""Duplas de teste da Fase 2: modelo falso com ferramentas e transporte HTTP falso."""

import json
from collections.abc import Callable
from typing import Any

import httpx
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage


class ModeloFalsoComFerramentas(FakeMessagesListChatModel):
    """Emite o roteiro de AIMessage em ordem (repete o roteiro ao terminar).

    `bind_tools` devolve o próprio modelo; cada chamada registra as mensagens recebidas
    em `chamadas`, para os testes inspecionarem o que "foi enviado ao modelo".
    """

    chamadas: list[list[BaseMessage]] = []

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ModeloFalsoComFerramentas":
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.chamadas.append(list(messages))
        resultado = super()._generate(messages, stop, run_manager, **kwargs)
        mensagem_gerada = resultado.generations[0].message
        # id único por emissão: o roteiro cicla e o agente ignora ids de chamadas já respondidas
        novas = [
            {**pedido, "id": f"{pedido['id']}-{len(self.chamadas)}"}
            for pedido in mensagem_gerada.tool_calls
        ]
        resultado.generations[0].message = mensagem_gerada.model_copy(update={"tool_calls": novas})
        return resultado


def chamada(nome: str, args: dict, id_: str = "c1") -> AIMessage:
    """AIMessage que pede uma ferramenta."""
    return AIMessage(content="", tool_calls=[{"name": nome, "args": args, "id": id_}])


def roteiro(*mensagens: AIMessage | str) -> ModeloFalsoComFerramentas:
    """Modelo falso com o roteiro dado (str vira AIMessage de texto)."""
    respostas = [AIMessage(content=item) if isinstance(item, str) else item for item in mensagens]
    return ModeloFalsoComFerramentas(responses=respostas, chamadas=[])


def cliente_http(resposta: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    """httpx.Client sem rede: cada requisição passa por `resposta`."""
    return httpx.Client(transport=httpx.MockTransport(resposta))


def resposta_json(dados: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status, content=json.dumps(dados), headers={"content-type": "application/json"}
    )
