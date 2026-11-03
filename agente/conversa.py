"""Memória de curto prazo: `RunnableWithMessageHistory` em volta do pipeline.

Cada conversa é uma `Sessao` (`session_id = uuid4`). O histórico de cada sessão fica num
`InMemoryChatMessageHistory`, num dicionário por `session_id`. Antes de chegar ao pipeline, o
histórico passa pelo filtro de relevância e por uma janela deslizante (`trim_messages`). Acima de
`limite` mensagens, as antigas viram um resumo (mensagem de sistema no começo do histórico) e só
as últimas `manter` ficam. Depois de cada turno, o objeto `Sessao` recebido é atualizado no lugar
(turnos e serviço).
"""

import warnings
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from operator import itemgetter
from uuid import uuid4

from langchain_core._api import LangChainDeprecationWarning
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    get_buffer_string,
    trim_messages,
)
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.runnables.history import RunnableWithMessageHistory

from agente.mascara import mascarar
from agente.prompts import prompt_avaliacao, prompt_resumo
from agente.schemas import AvaliacaoRelevancia, RespostaTurno, Sessao

__all__ = [
    "Conversa",
    "abrir_sessao",
    "montar_avaliacao_relevancia",
    "montar_conversa",
    "texto_resposta",
]

# Intenções que não entram na conversa guardada (camada 2 de guardrail).
INTENCOES_NAO_GUARDADAS = {"conteudo_proibido", "tentativa_de_injecao"}


def abrir_sessao(
    cenario: str | None = None,
    servico: str | None = None,
    agora: Callable[[], datetime] = datetime.now,
) -> Sessao:
    """Sessão nova com `session_id` único (um por incidente)."""
    return Sessao(
        session_id=str(uuid4()), criada_em=agora(), servico=servico, cenario=cenario, turnos=0
    )


def texto_resposta(resposta: RespostaTurno) -> str:
    """Texto curto da resposta do agente, para entrar no histórico da conversa."""
    if resposta.fixa:
        return resposta.fixa.texto
    if resposta.analise:
        hipoteses = [f"- {hip.causa} ({hip.confianca:.2f})" for hip in resposta.analise.hipoteses]
        return "\n".join([resposta.analise.resumo, *hipoteses])
    return resposta.erro or ""


def _bloqueada(resposta: RespostaTurno) -> bool:
    """Moderação (camada 1), conteúdo proibido e injeção não entram na conversa guardada."""
    if resposta.fixa and resposta.fixa.camada == 1:
        return True
    return resposta.nlu is not None and resposta.nlu.intencao in INTENCOES_NAO_GUARDADAS


def montar_avaliacao_relevancia(llm) -> Runnable:
    """Filtro de relevância: prompt | LLM com saída estruturada AvaliacaoRelevancia."""
    return prompt_avaliacao | llm.with_structured_output(AvaliacaoRelevancia)


def _avaliar(avaliar_relevancia: Runnable | None, texto: str) -> dict:
    """Relevância e motivo da mensagem; sem avaliador ou com erro dele, vale `alta`."""
    if avaliar_relevancia is None:
        return {"relevancia": "alta", "motivo": "sem avaliador de relevância"}
    try:
        avaliacao = avaliar_relevancia.invoke({"mensagem": texto})
    except Exception as erro:  # noqa: BLE001 - na dúvida, a mensagem fica no contexto
        return {"relevancia": "alta", "motivo": f"falha na avaliação: {erro}"}
    return {"relevancia": avaliacao.nivel, "motivo": avaliacao.motivo}


def _relevante(mensagem: BaseMessage) -> bool:
    return mensagem.additional_kwargs.get("relevancia") != "baixa"


def _e_resumo(mensagem: BaseMessage) -> bool:
    return "resumo" in mensagem.additional_kwargs


def _sessao_atualizada(sessao: Sessao, resposta: RespostaTurno) -> Sessao:
    servico = None if _bloqueada(resposta) or not resposta.nlu else resposta.nlu.servico
    return sessao.model_copy(
        update={"turnos": sessao.turnos + 1, "servico": servico or sessao.servico}
    )


@contextmanager
def _sem_aviso_de_depreciacao():
    """Silencia só o aviso de depreciação das duas classes de histórico, só nesta chamada.

    O `RunnableWithMessageHistory` e o `InMemoryChatMessageHistory` são o padrão de memória de
    conversa do projeto e estão marcados como deprecados no langchain-core 1.x; a justificativa
    está em specs/003-fase3-memoria/research.md (D9b) e no notebook (seção 3.3)."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r".*(RunnableWithMessageHistory|InMemoryChatMessageHistory).*",
            category=LangChainDeprecationWarning,
        )
        yield


class Conversa:
    """Conversas por sessão: histórico por `session_id`, janela, filtro de relevância e resumo."""

    def __init__(
        self,
        pipeline: Runnable,
        llm_resumo,
        avaliar_relevancia: Runnable | None = None,
        limite: int = 8,
        manter: int = 4,
        max_tokens_janela: int = 2000,
    ):
        self._avaliar_relevancia = avaliar_relevancia
        self._limite, self._manter = limite, manter
        self._resumidor = prompt_resumo | llm_resumo | StrOutputParser()
        self._historicos: dict[str, InMemoryChatMessageHistory] = {}
        self._sessoes: dict[str, Sessao] = {}
        self._pipeline = pipeline
        # Janela deslizante: as últimas mensagens que cabem em `max_tokens_janela`.
        # Sem modelo para contar tokens, usa a contagem aproximada.
        limitador = trim_messages(
            max_tokens=max_tokens_janela,
            strategy="last",
            token_counter=count_tokens_approximately,
            include_system=True,
            allow_partial=False,
            start_on="human",
        )
        cadeia = {
            "mensagem": itemgetter("mensagem"),
            "session_id": itemgetter("session_id"),
            "historico": lambda x: limitador.invoke(list(filter(_relevante, x["historico"]))),
        } | RunnableLambda(self._turno)
        # O turno guarda o par (pergunta mascarada, resposta) em "novas". `guardar_entrada` é
        # uma lista vazia de propósito: o `RunnableWithMessageHistory` guarda a entrada em
        # `input_messages_key` (_exit_history) e assim não guarda a mensagem crua, sem máscara.
        with _sem_aviso_de_depreciacao():
            self._com_historico = RunnableWithMessageHistory(
                cadeia,
                self.obter_historico_sessao,
                input_messages_key="guardar_entrada",
                history_messages_key="historico",
                output_messages_key="novas",
            )

    def obter_historico_sessao(self, session_id: str) -> InMemoryChatMessageHistory:
        """Histórico da sessão (criado na primeira vez); é o `get_session_history` do
        `RunnableWithMessageHistory`."""
        if session_id not in self._historicos:
            with _sem_aviso_de_depreciacao():
                self._historicos[session_id] = InMemoryChatMessageHistory()
        return self._historicos[session_id]

    def _turno(self, entrada: dict) -> dict:
        """Roda o pipeline e devolve a resposta com as mensagens novas a guardar."""
        mensagem = entrada["mensagem"]
        resposta = self._pipeline.invoke(
            {
                "mensagem": mensagem,
                "historico": entrada["historico"],
                "incidente_id": entrada["session_id"],
                "session_id": entrada["session_id"],
            }
        )
        novas: list[BaseMessage] = []
        if not _bloqueada(resposta) and mensagem.strip():
            pergunta, texto = mascarar(mensagem), texto_resposta(resposta)
            novas = [
                HumanMessage(
                    pergunta, additional_kwargs=_avaliar(self._avaliar_relevancia, pergunta)
                ),
                AIMessage(texto, additional_kwargs=_avaliar(self._avaliar_relevancia, texto)),
            ]
        return {"resposta": resposta, "novas": novas}

    def _resumir_se_preciso(self, historico: InMemoryChatMessageHistory) -> None:
        """Acima de `limite` mensagens, resume as antigas e mantém as últimas `manter`."""
        mensagens = historico.messages
        resumo_atual = next((msg for msg in mensagens if _e_resumo(msg)), None)
        guardadas = [msg for msg in mensagens if not _e_resumo(msg)]
        if len(guardadas) <= self._limite:
            return
        antigas, recentes = guardadas[: -self._manter], guardadas[-self._manter :]
        anterior = resumo_atual.additional_kwargs["resumo"] if resumo_atual else "(none)"
        try:
            resumo = self._resumidor.invoke(
                {
                    "resumo": anterior,
                    "conversa": get_buffer_string(list(filter(_relevante, antigas))),
                }
            )
        except Exception:  # falha do modelo: mantém tudo e segue
            return
        historico.clear()
        historico.add_message(
            SystemMessage(
                f"Summary of the earlier conversation:\n{resumo}",
                additional_kwargs={"resumo": resumo},
            )
        )
        historico.add_messages(recentes)

    def estado(self, sessao: Sessao) -> dict:
        """Estado da sessão: mensagens sem o resumo, resumo e sessao (vazios antes do 1º turno)."""
        mensagens = self.obter_historico_sessao(sessao.session_id).messages
        resumo = next((msg for msg in mensagens if _e_resumo(msg)), None)
        return {
            "mensagens": [msg for msg in mensagens if not _e_resumo(msg)],
            "resumo": resumo.additional_kwargs["resumo"] if resumo else "",
            "sessao": self._sessoes.get(sessao.session_id, sessao),
        }

    def turno(self, sessao: Sessao, mensagem: str) -> RespostaTurno:
        """Processa um turno; os metadados guardados mandam e `sessao` é atualizada no lugar."""
        base = self.estado(sessao)["sessao"]
        config = {"configurable": {"session_id": sessao.session_id}}
        saida = self._com_historico.invoke(
            {"mensagem": mensagem, "session_id": sessao.session_id, "guardar_entrada": []},
            config,
        )
        resposta = saida["resposta"]
        self._resumir_se_preciso(self.obter_historico_sessao(sessao.session_id))
        atualizada = _sessao_atualizada(base, resposta)
        self._sessoes[sessao.session_id] = atualizada
        for campo, valor in atualizada:
            setattr(sessao, campo, valor)
        return resposta


def montar_conversa(
    pipeline: Runnable,
    llm_resumo,
    avaliar_relevancia: Runnable | None = None,
    limite: int = 8,
    manter: int = 4,
    max_tokens_janela: int = 2000,
) -> Conversa:
    """Conversa com `RunnableWithMessageHistory`; resume acima de `limite` mensagens.

    Com `avaliar_relevancia`, cada mensagem guardada é classificada (baixa, alta, critica) e as
    `baixa` ficam fora do histórico enviado ao pipeline, que também é cortado pela janela de
    `max_tokens_janela` tokens."""
    return Conversa(pipeline, llm_resumo, avaliar_relevancia, limite, manter, max_tokens_janela)
