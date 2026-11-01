"""Pipeline LCEL da Fase 1: máscara -> moderação -> NLU -> roteamento -> investigação."""
from typing import Callable

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import Runnable, RunnableBranch, RunnableLambda, RunnablePassthrough

from agente.mascara import mascarar
from agente.preprocessamento import preprocessar
from agente.prompts import montar_nlu, prompt_investigacao, respostas_fixas
from agente.schemas import (
    AnaliseIncidente, ResultadoModeracao, RespostaFixa, RespostaTurno,
)

# Intenções que recebem resposta fixa (camada 2). Ponto de extensão da US2.
INTENCOES_FIXAS = {
    "saudacao", "fora_do_escopo", "conteudo_proibido", "pedido_de_acao",
    "tentativa_de_injecao", "gerar_relatorio", "confirmar_causa",
}


def _texto_fixo(categoria: str) -> str:
    """Texto do PromptTemplate da categoria."""
    return respostas_fixas[categoria].format()


def _fixa(camada: int, categoria: str) -> RespostaFixa:
    return RespostaFixa(texto=_texto_fixo(categoria), camada=camada, categoria=categoria)


def _mascarar_entrada(entrada: dict) -> dict:
    """Mascara a mensagem e o histórico antes de qualquer envio externo (FR-000)."""
    historico = [
        m.model_copy(update={"content": mascarar(m.content)}) if isinstance(m.content, str) else m
        for m in entrada.get("historico") or []
    ]
    return {"mensagem": mascarar(entrada.get("mensagem") or ""), "historico": historico}


def _resp_vazia(estado: dict) -> RespostaTurno:
    mod = ResultadoModeracao(status="pulada", motivo="mensagem vazia")
    return RespostaTurno(rota="fixa", moderacao=mod, fixa=_fixa(2, "vazia"))


def _resp_sinalizada(estado: dict) -> RespostaTurno:
    return RespostaTurno(rota="fixa", moderacao=estado["moderacao"], fixa=_fixa(1, "sinalizada"))


def _resp_fixa_nlu(estado: dict) -> RespostaTurno:
    nlu = estado["nlu"]
    return RespostaTurno(rota="fixa", moderacao=estado["moderacao"], nlu=nlu,
                         fixa=_fixa(2, nlu.intencao))


def _resp_investigacao(estado: dict) -> RespostaTurno:
    res = estado["resultado"]
    base = dict(moderacao=estado["moderacao"], nlu=estado["nlu"])
    if isinstance(res, str):
        return RespostaTurno(rota="erro", erro=res, **base)
    return RespostaTurno(rota="investigacao", analise=res, **base)


def _preprocessar_estado(estado: dict) -> dict:
    """Aplica preprocessar ao estado e devolve as variáveis do prompt de investigação."""
    nlu = estado.get("nlu")
    erro = preprocessar(estado["mensagem"], nlu.servico if nlu else None)
    i = erro.impressao
    return {
        "texto_limpo": erro.texto_limpo, "excecao": i.excecao or "não identificada",
        "primeiro_frame": i.primeiro_frame or "não identificado",
        "servico": i.servico or "não identificado", "historico": estado.get("historico", []),
    }


def montar_investigacao(llm) -> Runnable:
    """Estado -> AnaliseIncidente (uma nova tentativa); falha final vira str com o erro."""
    parser = JsonOutputParser(pydantic_object=AnaliseIncidente)
    nucleo = (
        RunnableLambda(_preprocessar_estado)
        | prompt_investigacao.partial(format_instructions=parser.get_format_instructions())
        | llm | parser
        | RunnableLambda(AnaliseIncidente.model_validate)
    ).with_retry(stop_after_attempt=2, wait_exponential_jitter=False)
    falha = RunnableLambda(
        lambda e: f"JSON inválido da investigação: {e['excecao']} | mensagem: {e['mensagem']}"
    )
    return nucleo.with_fallbacks([falha], exception_key="excecao")


def montar_pipeline(
    llm, moderar: Callable[[str], ResultadoModeracao],
    nlu: Runnable | None = None, investigacao: Runnable | None = None,
) -> Runnable:
    """Entrada {"mensagem", "historico"} -> RespostaTurno. nlu/investigacao injetáveis."""
    nlu = nlu or montar_nlu(llm)
    investigacao = investigacao or montar_investigacao(llm)
    investigar = RunnablePassthrough.assign(resultado=investigacao) | RunnableLambda(_resp_investigacao)
    apos_nlu = RunnableBranch(
        (lambda e: e["nlu"].intencao in INTENCOES_FIXAS, RunnableLambda(_resp_fixa_nlu)),
        investigar,
    )
    apos_moderacao = RunnableBranch(
        (lambda e: e["moderacao"].status == "sinalizada", RunnableLambda(_resp_sinalizada)),
        RunnablePassthrough.assign(nlu=nlu) | apos_nlu,
    )
    moderada = RunnablePassthrough.assign(moderacao=lambda e: moderar(e["mensagem"])) | apos_moderacao
    return RunnableLambda(_mascarar_entrada) | RunnableBranch(
        (lambda e: not e["mensagem"].strip(), RunnableLambda(_resp_vazia)),
        moderada,
    )
