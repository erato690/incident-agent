"""Pipeline LCEL da Fase 1: máscara -> moderação -> NLU -> roteamento -> investigação."""

from collections.abc import Callable

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable, RunnableBranch, RunnableLambda, RunnablePassthrough

from agente.mascara import mascarar
from agente.preprocessamento import preprocessar
from agente.prompts import montar_nlu, prompt_investigacao, respostas_fixas
from agente.schemas import (
    AnaliseIncidente,
    RespostaFixa,
    RespostaTurno,
    ResultadoInvestigacao,
    ResultadoModeracao,
)

# Intenções que recebem resposta fixa (camada 2). Ponto de extensão da US2.
INTENCOES_FIXAS = {
    "saudacao",
    "fora_do_escopo",
    "conteudo_proibido",
    "pedido_de_acao",
    "tentativa_de_injecao",
    "gerar_relatorio",
    "confirmar_causa",
}


def _texto_fixo(categoria: str) -> str:
    """Texto do PromptTemplate da categoria."""
    return respostas_fixas[categoria].format()


def _fixa(camada: int, categoria: str) -> RespostaFixa:
    return RespostaFixa(texto=_texto_fixo(categoria), camada=camada, categoria=categoria)


def _mascarar_entrada(entrada: dict) -> dict:
    """Mascara a mensagem e o histórico antes de qualquer envio externo (FR-000)."""
    historico = [
        msg.model_copy(update={"content": mascarar(msg.content)})
        if isinstance(msg.content, str)
        else msg
        for msg in entrada.get("historico") or []
    ]
    return {"mensagem": mascarar(entrada.get("mensagem") or ""), "historico": historico}


def _resp_vazia(estado: dict) -> RespostaTurno:
    mod = ResultadoModeracao(status="pulada", motivo="mensagem vazia")
    return RespostaTurno(rota="fixa", moderacao=mod, fixa=_fixa(2, "vazia"))


def _resp_sinalizada(estado: dict) -> RespostaTurno:
    return RespostaTurno(rota="fixa", moderacao=estado["moderacao"], fixa=_fixa(1, "sinalizada"))


def _resp_fixa_nlu(estado: dict) -> RespostaTurno:
    nlu = estado["nlu"]
    return RespostaTurno(
        rota="fixa", moderacao=estado["moderacao"], nlu=nlu, fixa=_fixa(2, nlu.intencao)
    )


def _resp_investigacao(estado: dict) -> RespostaTurno:
    resultado = estado["resultado"]
    base = {"moderacao": estado["moderacao"], "nlu": estado["nlu"]}
    if isinstance(resultado, ResultadoInvestigacao):  # com agente: traz a trajetória
        base["trajetoria"] = resultado.trajetoria
        resultado = resultado.erro if resultado.erro is not None else resultado.analise
    if isinstance(resultado, str):
        return RespostaTurno(rota="erro", erro=resultado, **base)
    return RespostaTurno(rota="investigacao", analise=resultado, **base)


def _preprocessar_estado(estado: dict) -> dict:
    """Aplica preprocessar ao estado e devolve as variáveis do prompt de investigação."""
    nlu = estado.get("nlu")
    erro = preprocessar(estado["mensagem"], nlu.servico if nlu else None)
    impressao = erro.impressao
    return {
        "texto_limpo": erro.texto_limpo,
        "excecao": impressao.excecao or "não identificada",
        "primeiro_frame": impressao.primeiro_frame or "não identificado",
        "servico": impressao.servico or "não identificado",
        "historico": estado.get("historico", []),
    }


def montar_investigacao_json(llm) -> Runnable:
    """Estado -> dict JSON da análise, sem validação; usado no stream (JSON parcial)."""
    parser = JsonOutputParser(pydantic_object=AnaliseIncidente)
    return (
        RunnableLambda(_preprocessar_estado)
        | prompt_investigacao.partial(format_instructions=parser.get_format_instructions())
        | llm
        | parser
    )


def montar_investigacao(llm) -> Runnable:
    """Estado -> AnaliseIncidente (uma nova tentativa); falha final vira str com o erro."""
    nucleo = (
        montar_investigacao_json(llm) | RunnableLambda(AnaliseIncidente.model_validate)
    ).with_retry(stop_after_attempt=2, wait_exponential_jitter=False)
    falha = RunnableLambda(
        lambda estado: (
            f"JSON inválido da investigação: {estado['excecao']} | mensagem: {estado['mensagem']}"
        )
    )
    return nucleo.with_fallbacks([falha], exception_key="excecao")


def _ja_respondido(estado: dict) -> bool:
    """True quando algum passo anterior já deixou a resposta pronta em estado["resposta"]."""
    return estado.get("resposta") is not None


def _se_pendente(runnable: Runnable) -> Runnable:
    """Roda o passo só se ainda não há resposta; com resposta pronta, o estado passa direto."""
    return RunnableBranch((_ja_respondido, RunnablePassthrough()), runnable)


def _marcar(decide: Callable[[dict], RespostaTurno | None]) -> Runnable:
    """Acrescenta a chave "resposta" (RespostaTurno ou None) sem perder as outras."""
    return RunnablePassthrough.assign(resposta=RunnableLambda(decide))


def _decide_vazia(estado: dict) -> RespostaTurno | None:
    return None if estado["mensagem"].strip() else _resp_vazia(estado)


def _decide_moderacao(estado: dict) -> RespostaTurno | None:
    return _resp_sinalizada(estado) if estado["moderacao"].status == "sinalizada" else None


def _decide_roteador(estado: dict) -> RespostaTurno | None:
    return _resp_fixa_nlu(estado) if estado["nlu"].intencao in INTENCOES_FIXAS else None


def montar_etapas(
    llm,
    moderar: Callable[[str], ResultadoModeracao],
    nlu: Runnable | None = None,
    investigacao: Runnable | None = None,
) -> dict[str, Runnable]:
    """Etapas do pipeline na ordem em que a mensagem passa (cada uma é um Runnable)."""
    nlu = nlu or montar_nlu(llm)
    investigacao = investigacao or montar_investigacao(llm)
    etapas = {
        # entra {mensagem, historico} -> sai {mensagem, historico} com segredos mascarados
        "passo1_mascara": RunnableLambda(_mascarar_entrada),
        # entra estado mascarado -> sai estado + resposta (fixa "vazia" ou None)
        "passo2_vazia": _se_pendente(_marcar(_decide_vazia)),  # 1ª checagem: sempre roda
        # entra estado sem resposta -> sai estado + moderacao + resposta (fixa se sinalizada)
        "passo3_moderacao": _se_pendente(
            RunnablePassthrough.assign(moderacao=lambda estado: moderar(estado["mensagem"]))
            | _marcar(_decide_moderacao)
        ),
        # entra estado sem resposta -> sai estado + nlu (AnaliseNLU)
        "passo4_nlu": _se_pendente(RunnablePassthrough.assign(nlu=nlu)),
        # entra estado + nlu -> sai estado + resposta (fixa se a intenção for de resposta fixa)
        "passo5_roteador": _se_pendente(_marcar(_decide_roteador)),
        # entra estado sem resposta -> sai estado + resposta (investigação ou erro)
        "passo6_investigacao": _se_pendente(
            RunnablePassthrough.assign(resultado=investigacao) | _marcar(_resp_investigacao)
        ),
        # entra estado com resposta -> sai só o RespostaTurno
        "passo7_resposta": RunnableLambda(lambda estado: estado["resposta"]),
    }
    for nome, etapa in etapas.items():
        etapa.name = nome  # nome legível no grafo (get_graph) e no trace
    return etapas


def montar_pipeline(
    llm,
    moderar: Callable[[str], ResultadoModeracao],
    nlu: Runnable | None = None,
    investigacao: Runnable | None = None,
) -> Runnable:
    """Entrada {"mensagem", "historico"} -> RespostaTurno. nlu/investigacao injetáveis."""
    (
        passo1_mascara,
        passo2_vazia,
        passo3_moderacao,
        passo4_nlu,
        passo5_roteador,
        passo6_investigacao,
        passo7_resposta,
    ) = montar_etapas(llm, moderar, nlu, investigacao).values()
    return (
        passo1_mascara
        | passo2_vazia
        | passo3_moderacao
        | passo4_nlu
        | passo5_roteador
        | passo6_investigacao
        | passo7_resposta
    )
