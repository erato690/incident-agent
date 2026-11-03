"""Pipeline LCEL da Fase 1: máscara -> moderação -> NLU -> roteamento -> investigação."""

import re
from collections.abc import Callable

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable, RunnableBranch, RunnableLambda, RunnablePassthrough
from langchain_core.runnables.config import patch_config

from agente.agente_react import montar_registrador
from agente.ferramentas import CHAVE_CONTEXTO, montar_ferramentas_memoria
from agente.mascara import mascarar
from agente.memoria import MemoriaLongoPrazo
from agente.preprocessamento import preprocessar
from agente.prompts import (
    montar_nlu,
    montar_resolucao_memoria,
    prompt_investigacao,
    respostas_fixas,
    texto_causa_registrada,
    texto_causa_trocada,
)
from agente.schemas import (
    AnaliseIncidente,
    ContextoTurno,
    EpisodioEncontrado,
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


def _mascarar_opcional(texto: str | None) -> str | None:
    return mascarar(texto) if texto else texto


def _mascarar_entrada(entrada: dict) -> dict:
    """Mascara a mensagem e o histórico antes de qualquer envio externo (FR-000)."""
    historico = [
        msg.model_copy(update={"content": mascarar(msg.content)})
        if isinstance(msg.content, str)
        else msg
        for msg in entrada.get("historico") or []
    ]
    return {
        "mensagem": mascarar(entrada.get("mensagem") or ""),
        "historico": historico,
        "incidente_id": _mascarar_opcional(entrada.get("incidente_id")),
        "session_id": _mascarar_opcional(entrada.get("session_id")),
    }


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


def _resp_pedido(estado: dict, categoria: str) -> RespostaTurno:
    return RespostaTurno(
        rota="fixa", moderacao=estado["moderacao"], nlu=estado["nlu"], fixa=_fixa(2, categoria)
    )


def _falta_dado(estado: dict) -> str | None:
    """Categoria da resposta fixa que pede o dado sem o qual não se registra a causa."""
    if not estado.get("incidente_id"):
        return "pedir_incidente"
    if not estado["nlu"].servico:
        return "pedir_servico"
    return None if estado.get("session_id") else "pedir_sessao"


def _decide_roteador(memoria: MemoriaLongoPrazo | None) -> Callable[[dict], RespostaTurno | None]:
    """Com memória, confirmar_causa segue para o passo 6, se houver serviço e incidente."""
    fixas = INTENCOES_FIXAS - {"confirmar_causa"} if memoria else INTENCOES_FIXAS

    def decide(estado: dict) -> RespostaTurno | None:
        intencao = estado["nlu"].intencao
        if intencao in fixas:
            return _resp_fixa_nlu(estado)
        faltando = _falta_dado(estado) if memoria and intencao == "confirmar_causa" else None
        return _resp_pedido(estado, faltando) if faltando else None

    return decide


def _contexto_do_estado(estado: dict) -> ContextoTurno:
    """Contexto que trava as ferramentas de memória; vem do estado, nunca do modelo."""
    nlu = estado["nlu"]
    return ContextoTurno(
        intencao=nlu.intencao,
        servico=nlu.servico,
        incidente_id=estado.get("incidente_id"),
        session_id=estado.get("session_id"),
    )


def _palavras(texto: str | None) -> set[str]:
    return {palavra for palavra in re.findall(r"\w+", (texto or "").lower()) if len(palavra) >= 4}


def _citacao(achado: EpisodioEncontrado) -> str:
    episodio = achado.episodio
    return (
        f"consultar_memoria: incidente {episodio.incidente_id} em {episodio.criado_em:%Y-%m-%d}: "
        f"{episodio.causa} (histórico, não é observação atual)"
    )


def citar_episodios(
    analise: AnaliseIncidente, achados: list[EpisodioEncontrado]
) -> AnaliseIncidente:
    """SC-002: cada episódio que `consultar_memoria` devolveu acima do limiar entra na evidência
    da hipótese com mais palavras em comum com a causa do episódio (nenhuma em comum: não entra).
    Determinístico; não depende de o modelo citar o id e a data."""
    hipoteses = [hipotese.model_copy() for hipotese in analise.hipoteses]
    for achado in achados:
        causa = _palavras(achado.episodio.causa)
        comuns = [len(causa & _palavras(f"{h.causa} {h.evidencia}")) for h in hipoteses]
        if not comuns or max(comuns) == 0:
            continue
        alvo = hipoteses[comuns.index(max(comuns))]
        if achado.episodio.incidente_id in (alvo.evidencia or ""):
            continue
        alvo.evidencia = "; ".join(filter(None, [alvo.evidencia, _citacao(achado)]))
    return analise.model_copy(update={"hipoteses": hipoteses})


def _com_episodios_citados(resultado: object, contexto: ContextoTurno) -> object:
    if not contexto.episodios_consultados:
        return resultado
    if isinstance(resultado, AnaliseIncidente):
        return citar_episodios(resultado, contexto.episodios_consultados)
    if isinstance(resultado, ResultadoInvestigacao) and resultado.analise is not None:
        analise = citar_episodios(resultado.analise, contexto.episodios_consultados)
        return resultado.model_copy(update={"analise": analise})
    return resultado


def _investigar_com_contexto(investigacao: Runnable) -> Callable[[dict, dict], object]:
    def investigar(estado: dict, config: dict) -> object:
        contexto = _contexto_do_estado(estado)
        configurado = patch_config(config, configurable={CHAVE_CONTEXTO: contexto})
        return _com_episodios_citados(investigacao.invoke(estado, configurado), contexto)

    return investigar


def _resp_erro_registro(estado: dict, motivo: str, contexto: ContextoTurno) -> RespostaTurno:
    erro = f"Não consegui registrar a causa, nada foi registrado: {mascarar(motivo)}"
    return RespostaTurno(
        rota="erro",
        moderacao=estado["moderacao"],
        nlu=estado["nlu"],
        erro=erro,
        trajetoria=contexto.trajetoria,
    )


def _resp_registro(estado: dict, contexto: ContextoTurno) -> RespostaTurno:
    registro = contexto.registro
    episodio, anterior = registro.episodio, registro.arquivado
    dados = {"servico": episodio.servico, "causa": episodio.causa}
    texto = (
        texto_causa_trocada.format(anterior=anterior.causa, **dados)
        if anterior
        else texto_causa_registrada.format(**dados)
    )
    fixa = RespostaFixa(texto=texto, camada=2, categoria="confirmar_causa")
    return RespostaTurno(
        rota="memoria",
        moderacao=estado["moderacao"],
        nlu=estado["nlu"],
        fixa=fixa,
        episodio=episodio,
        episodio_anterior=anterior,
        resolucao=registro.decisao,
        trajetoria=contexto.trajetoria,
    )


def _entregar_ao_registro(registro: Runnable) -> Callable[[dict, dict], RespostaTurno]:
    """Passo 6 da confirmação: o Registrador decide chamar `gravar_episodio` (a trava
    da ferramenta confere o contexto) e a resposta lê o resultado do contexto do turno."""

    def entregar(estado: dict, config: dict) -> RespostaTurno:
        contexto = _contexto_do_estado(estado)
        configurado = patch_config(config, configurable={CHAVE_CONTEXTO: contexto})
        try:
            registro.invoke(estado, configurado)
        except Exception as excecao:  # erro legível, nada registrado (padrão with_fallbacks)
            return _resp_erro_registro(estado, str(excecao), contexto)
        if contexto.registro is None:
            motivo = contexto.erro_registro or "o agente não gravou o episódio (gravar_episodio)"
            return _resp_erro_registro(estado, motivo, contexto)
        return _resp_registro(estado, contexto)

    return entregar


def _registrador_padrao(llm, memoria: MemoriaLongoPrazo) -> Runnable:
    ferramentas = montar_ferramentas_memoria(memoria, montar_resolucao_memoria(llm))
    return montar_registrador(llm, ferramentas)


def _passo6_com_memoria(
    llm, memoria: MemoriaLongoPrazo, investigacao: Runnable, registro: Runnable | None
) -> Runnable:
    """Confirmação vai ao Registrador; o resto, à investigação com o contexto do turno."""
    registro = registro or _registrador_padrao(llm, memoria)
    investigar = RunnablePassthrough.assign(
        resultado=RunnableLambda(_investigar_com_contexto(investigacao))
    ) | _marcar(_resp_investigacao)
    return RunnableBranch(
        (
            lambda estado: estado["nlu"].intencao == "confirmar_causa",
            _marcar(_entregar_ao_registro(registro)),
        ),
        investigar,
    )


def montar_etapas(
    llm,
    moderar: Callable[[str], ResultadoModeracao],
    nlu: Runnable | None = None,
    investigacao: Runnable | None = None,
    memoria: MemoriaLongoPrazo | None = None,
    registro: Runnable | None = None,
) -> dict[str, Runnable]:
    """Etapas do pipeline na ordem em que a mensagem passa (cada uma é um Runnable)."""
    nlu = nlu or montar_nlu(llm)
    investigacao = investigacao or montar_investigacao(llm)
    if memoria is None:
        passo6 = RunnablePassthrough.assign(resultado=investigacao) | _marcar(_resp_investigacao)
    else:
        passo6 = _passo6_com_memoria(llm, memoria, investigacao, registro)
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
        "passo5_roteador": _se_pendente(_marcar(_decide_roteador(memoria))),
        # entra estado sem resposta -> sai estado + resposta (investigação ou erro)
        "passo6_investigacao": _se_pendente(passo6),
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
    memoria: MemoriaLongoPrazo | None = None,
    registro: Runnable | None = None,
) -> Runnable:
    """Entrada {"mensagem", "historico", "incidente_id", "session_id"} -> RespostaTurno.

    nlu, investigacao e registro (Registrador) são injetáveis; sem memória o
    comportamento não muda.
    """
    (
        passo1_mascara,
        passo2_vazia,
        passo3_moderacao,
        passo4_nlu,
        passo5_roteador,
        passo6_investigacao,
        passo7_resposta,
    ) = montar_etapas(llm, moderar, nlu, investigacao, memoria, registro).values()
    return (
        passo1_mascara
        | passo2_vazia
        | passo3_moderacao
        | passo4_nlu
        | passo5_roteador
        | passo6_investigacao
        | passo7_resposta
    )
