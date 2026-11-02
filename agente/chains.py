"""Composições LCEL da US2: sequencial, paralela, roteamento moderno e clássico."""

from langchain_classic.chains.router import MultiPromptChain
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    Runnable,
    RunnableBranch,
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)

from agente.loja import resumir_deploys, resumir_logs, resumir_metricas
from agente.preprocessamento import preprocessar

prompt_analise = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an SRE. Analyze the error in up to 3 sentences: probable cause and where "
            "to look. "
            "Always answer in Brazilian Portuguese.",
        ),
        ("human", "Erro:\n{preprocessado}"),
    ]
)
prompt_resumo = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Summarize the analysis in one short sentence for the on-call engineer. "
            "Always answer in Brazilian Portuguese.",
        ),
        ("human", "Análise:\n{analise}"),
    ]
)


def montar_chain_sequencial(llm) -> Runnable:
    """Entrada {"texto"} -> {texto, preprocessado, analise, resumo}, uma etapa após a outra."""
    return (
        RunnablePassthrough.assign(
            preprocessado=RunnableLambda(lambda estado: preprocessar(estado["texto"]).texto_limpo)
        )
        | RunnablePassthrough.assign(analise=prompt_analise | llm | StrOutputParser())
        | RunnablePassthrough.assign(resumo=prompt_resumo | llm | StrOutputParser())
    )


def montar_chain_paralela(fonte) -> Runnable:
    """Entrada {"servico"} -> {logs, metricas, deploys} (resumos), consultados em paralelo."""
    return RunnableParallel(
        logs=RunnableLambda(lambda estado: resumir_logs(fonte.logs(estado["servico"]))),
        metricas=RunnableLambda(lambda estado: resumir_metricas(fonte.metricas(estado["servico"]))),
        deploys=RunnableLambda(
            lambda estado: resumir_deploys(
                fonte.deploys(estado["servico"]), fonte.tags_do_servico()
            )
        ),
    )


def montar_roteador_moderno(destinos: dict[str, Runnable], padrao: Runnable) -> Runnable:
    """RunnableBranch por `estado["nlu"].intencao`; sem destino cai em `padrao`."""
    ramos = [
        (RunnableLambda(lambda estado, alvo=intencao: estado["nlu"].intencao == alvo), destino)
        for intencao, destino in destinos.items()
    ]
    return RunnableBranch(*ramos, padrao)


_DESTINOS_CLASSICOS = [
    {
        "name": "erro_de_codigo",
        "description": "Application bug: exception, stack trace, regression after a deploy",
        "prompt_template": "You are an SRE. Explain the likely code bug in 2 sentences. "
        "Always answer in Brazilian Portuguese.\n\n{input}",
    },
    {
        "name": "dependencia_externa",
        "description": "Third-party service failure: gateway, external API, network timeout",
        "prompt_template": "You are an SRE. Explain the external dependency failure in 2 "
        "sentences. "
        "Always answer in Brazilian Portuguese.\n\n{input}",
    },
    {
        "name": "infraestrutura",
        "description": "Infrastructure resources: memory, CPU, pod, disk, database",
        "prompt_template": "You are an SRE. Explain the infrastructure problem in 2 sentences. "
        "Always answer in Brazilian Portuguese.\n\n{input}",
    },
]


def montar_router_chain_classica(llm) -> MultiPromptChain:
    """API clássica: LLMRouterChain escolhe entre três prompts; saída em `text`."""
    padrao = ChatPromptTemplate.from_template(
        "Answer in 2 sentences as an SRE. Always answer in Brazilian Portuguese.\n\n{input}"
    )
    return MultiPromptChain.from_prompts(
        llm, _DESTINOS_CLASSICOS, default_chain=_cadeia_padrao(padrao, llm)
    )


def _cadeia_padrao(prompt, llm):
    from langchain_classic.chains import LLMChain

    return LLMChain(prompt=prompt, llm=llm, output_key="text")
