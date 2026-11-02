"""Agente clássico (ZERO_SHOT_REACT_DESCRIPTION): ferramentas de uma entrada e memória."""

from langchain_classic.memory import ConversationBufferMemory
from langchain_core.language_models.fake import FakeListLLM

from agente.classico import (
    MENSAGEM_FORMATO_INVALIDO,
    PREFIXO_CLASSICO,
    ferramentas_uma_entrada,
    montar_agente_classico,
)
from agente.loja import FonteLoja

FONTE = FonteLoja(
    {
        "cenario": {"id": "x"},
        "logs": {
            "total": 1,
            "truncado": False,
            "logs": [
                {
                    "horario": "2026-10-14T14:38:00-03:00",
                    "servico": "pagamentos-api",
                    "nivel": "ERROR",
                    "mensagem": "NPE em confirmar senha=Sup3r",
                }
            ],
        },
        "metricas": {
            "series": [
                {
                    "servico": "pagamentos-api",
                    "metrica": "erros_5xx",
                    "unidade": "erros/min",
                    "resumo": {"min": 0.0, "max": 9.0, "media": 3.0, "ultimo": 9.0},
                    "pontos": [],
                },
                {
                    "servico": "pagamentos-api",
                    "metrica": "cpu",
                    "unidade": "%",
                    "resumo": {"min": 20.0, "max": 30.0, "media": 25.0, "ultimo": 30.0},
                    "pontos": [],
                },
            ]
        },
        "deploys": {
            "deploys": [
                {
                    "horario": "2026-10-14T14:35:00-03:00",
                    "servico": "pagamentos-api",
                    "versao": "2.14.0",
                    "tag": "pagamentos-api/v2.14.0",
                    "commit": "6245f86",
                    "autor": "ana",
                    "mensagem": "cupom",
                }
            ]
        },
    }
)


def _por_nome(**opcoes):
    return {ferramenta.name: ferramenta for ferramenta in ferramentas_uma_entrada(FONTE, **opcoes)}


def test_ferramentas_aceitam_uma_entrada_de_texto():
    ferramentas = _por_nome(
        github=lambda base, nova: (_ for _ in ()).throw(RuntimeError(f"{base}|{nova}"))
    )
    assert set(ferramentas) == {
        "buscar_logs",
        "buscar_metricas",
        "listar_deploys",
        "comparar_versoes",
    }
    assert "NPE em confirmar" in ferramentas["buscar_logs"].run("pagamentos-api")
    assert "erros_5xx" in ferramentas["buscar_metricas"].run("pagamentos-api")
    assert "2.14.0" in ferramentas["listar_deploys"].run("pagamentos-api")
    so_cpu = ferramentas["buscar_metricas"].run("pagamentos-api cpu")
    assert "cpu" in so_cpu and "erros_5xx" not in so_cpu


def test_observacao_tem_prefixo_e_mascara():
    observacao = _por_nome()["buscar_logs"].run("pagamentos-api")
    assert observacao.startswith("TOOL DATA") and "Sup3r" not in observacao


def test_comparar_divide_a_entrada_em_duas_tags():
    vistas = []

    def gh(base, nova):
        vistas.append((base, nova))
        raise RuntimeError("sem rede")

    observacao = _por_nome(github=gh)["comparar_versoes"].run(
        "pagamentos-api/v2.13.4 pagamentos-api/v2.14.0"
    )
    assert vistas == [("pagamentos-api/v2.13.4", "pagamentos-api/v2.14.0")]
    assert "Tool error" in observacao


def test_comparar_com_entrada_errada_vira_texto():
    observacao = _por_nome()["comparar_versoes"].run("so-uma-tag")
    assert "two tags" in observacao


def test_agente_classico_monta_roda_e_guarda_o_turno():
    ferramentas = ferramentas_uma_entrada(FONTE)
    agente = montar_agente_classico(
        FakeListLLM(responses=["Final Answer: foi o deploy."]), ferramentas
    )
    assert agente.agent.__class__.__name__ == "ZeroShotAgent"
    assert isinstance(agente.memory, ConversationBufferMemory)
    assert agente.max_iterations == 8 and agente.early_stopping_method == "generate"
    assert agente.handle_parsing_errors == MENSAGEM_FORMATO_INVALIDO
    assert "{chat_history}" in agente.agent.llm_chain.prompt.template
    agente.invoke({"input": "pagamentos-api deu 500"})
    mensagens = agente.memory.load_memory_variables({})["chat_history"]
    assert "pagamentos-api deu 500" in mensagens and "foi o deploy" in mensagens


class _Espiao(FakeListLLM):
    prompts: list = []

    def _call(self, prompt, *args, **kwargs):
        self.prompts.append(prompt)
        return super()._call(prompt, *args, **kwargs)


def test_memoria_chega_ao_prompt_do_proximo_turno():
    llm = _Espiao(responses=["Final Answer: a", "Final Answer: b"], prompts=[])
    agente = montar_agente_classico(llm, ferramentas_uma_entrada(FONTE))
    agente.invoke({"input": "primeira pergunta"})
    agente.invoke({"input": "segunda"})
    assert "Human: primeira pergunta" not in llm.prompts[0]
    assert (
        "Human: primeira pergunta" in llm.prompts[1]
        and "AI: a" in llm.prompts[1]
        and PREFIXO_CLASSICO[:20] in llm.prompts[1]
    )


class _EspiaoStop(FakeListLLM):
    chamadas: list = []

    def _call(self, prompt, stop=None, *args, **kwargs):
        self.chamadas.append({"prompt": prompt, "stop": stop})
        return super()._call(prompt, stop, *args, **kwargs)


def test_stop_em_observation_chega_ao_modelo_e_prompt_exige_palavras_em_ingles():
    llm = _EspiaoStop(
        responses=[
            "Thought: ver deploys\nAction: listar_deploys\nAction Input: pagamentos-api",
            "Thought: pronto\nFinal Answer: foi o deploy.",
        ],
        chamadas=[],
    )
    agente = montar_agente_classico(llm, ferramentas_uma_entrada(FONTE))
    saida = agente.invoke({"input": "pagamentos-api deu 500"})
    assert saida["output"] == "foi o deploy."
    assert all("\nObservation:" in chamada["stop"] for chamada in llm.chamadas)
    prompt = llm.chamadas[0]["prompt"]
    assert "Final Answer:" in prompt and "Never write Observation:" in prompt
    assert "Human: " not in prompt and "{chat_history}" not in prompt


def test_formato_em_portugues_recebe_mensagem_curta_de_correcao():
    llm = _EspiaoStop(
        responses=["Pensamento: hmm\nResposta Final: x", "Thought: ok\nFinal Answer: certo"],
        chamadas=[],
    )
    agente = montar_agente_classico(llm, ferramentas_uma_entrada(FONTE))
    assert agente.invoke({"input": "oi"})["output"] == "certo"
    assert MENSAGEM_FORMATO_INVALIDO in llm.chamadas[1]["prompt"]


def test_descricao_de_comparar_versoes_da_o_formato_exato():
    descricao = _por_nome()["comparar_versoes"].description
    assert "<servico>/vX.Y.Z <servico>/vX.Y.Z" in descricao and "base tag first" in descricao


def test_listar_deploys_informa_a_tag_anterior():
    texto = _por_nome()["listar_deploys"].run("pagamentos-api")
    assert "pagamentos-api/v2.14.0 (previous: pagamentos-api/v2.13.4)" in texto
