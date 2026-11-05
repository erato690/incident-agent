import inspect

import langsmith

from agente import avaliacao
from agente.avaliacao import (
    auditor_aprovou,
    avaliar_localmente,
    causa_certa,
    exemplos_dataset,
    resumo_metricas,
    saida_do_turno,
    trajetoria_ferramentas,
)
from agente.schemas import (
    AnaliseIncidente,
    Hipotese,
    PassoTrajetoria,
    RespostaTurno,
    ResultadoModeracao,
)


def _resposta(causa="Pool de conexões esgotado", ferramentas=("buscar_logs",), **extra):
    analise = AnaliseIncidente(
        severidade="alta",
        categoria="x",
        resumo="r",
        hipoteses=[
            Hipotese(causa=causa, confianca=0.9, evidencia="e"),
            Hipotese(causa="outra", confianca=0.1, evidencia="e"),
        ],
        proximos_passos=["p"],
    )
    passos = [PassoTrajetoria(ferramenta=f, duracao_ms=1, tamanho=1) for f in ferramentas]
    return RespostaTurno(
        rota="investigacao",
        moderacao=ResultadoModeracao(status="ok"),
        analise=analise,
        trajetoria=passos,
        **extra,
    )


def test_exemplos_dataset_tem_8_itens_com_ferramentas():
    exemplos = exemplos_dataset()
    assert len(exemplos) == 8
    por_cenario = {e["inputs"]["cenario"]: e for e in exemplos}
    assert set(por_cenario["pool_esgotado"]["inputs"]) == {"mensagem", "cenario"}
    saidas = por_cenario["pool_esgotado"]["outputs"]
    assert saidas["palavras_causa"] == ["pool"] and saidas["causa_esperada"]
    assert "comparar_versoes" in saidas["ferramentas_esperadas"]
    esperadas = lambda c: por_cenario[c]["outputs"]["ferramentas_esperadas"]  # noqa: E731
    assert "consultar_estatisticas_banco" in esperadas("banco_lento_com_deploy")
    assert "consultar_wiki" in esperadas("rate_limit")


def test_saida_do_turno_serializavel():
    saida = saida_do_turno(_resposta(ferramentas=("a", "b")))
    assert saida == {
        "rota": "investigacao",
        "causa_principal": "Pool de conexões esgotado",
        "confianca": 0.9,
        "ferramentas": ["a", "b"],
        "auditoria_aprovada": None,
        "aviso": None,
    }
    vazia = saida_do_turno(RespostaTurno(rota="erro", moderacao=ResultadoModeracao(status="ok")))
    assert vazia["causa_principal"] is None and vazia["ferramentas"] == []


def test_causa_certa():
    ref = {"palavras_causa": ["POOL"]}
    assert causa_certa({}, {"causa_principal": "Pool esgotado"}, ref)["score"] == 1
    assert causa_certa({}, {"causa_principal": "Deploy ruim"}, ref)["score"] == 0
    assert causa_certa({}, {"causa_principal": None}, ref)["score"] == 0


def test_trajetoria_ferramentas_fracao_e_faltantes():
    ref = {"ferramentas_esperadas": ["a", "b", "c", "d"]}
    r = trajetoria_ferramentas({}, {"ferramentas": ["a", "b", "x"]}, ref)
    assert r["key"] == "trajetoria_ferramentas" and r["score"] == 0.5
    assert "c" in r["comment"] and "d" in r["comment"]
    assert (
        trajetoria_ferramentas({}, {"ferramentas": []}, {"ferramentas_esperadas": []})["score"] == 1
    )


def test_trajetoria_ferramenta_proibida(monkeypatch):
    monkeypatch.setattr(avaliacao, "FERRAMENTAS_PROIBIDAS", ["reiniciar_servico"])
    ref = {"ferramentas_esperadas": ["a"]}
    assert (
        trajetoria_ferramentas({}, {"ferramentas": ["a", "reiniciar_servico"]}, ref)["score"] == 0
    )


def test_auditor_aprovou():
    assert auditor_aprovou({}, {"auditoria_aprovada": True}, {})["score"] == 1
    assert auditor_aprovou({}, {"auditoria_aprovada": False}, {})["score"] == 0
    assert auditor_aprovou({}, {"auditoria_aprovada": None}, {})["score"] is None


def test_avaliadores_aceitos_pelo_langsmith_instalado():
    # o langsmith.evaluate aceita avaliadores com (inputs, outputs, reference_outputs)
    for func in (causa_certa, trajetoria_ferramentas, auditor_aprovou):
        assert list(inspect.signature(func).parameters) == [
            "inputs",
            "outputs",
            "reference_outputs",
        ]
    assert callable(langsmith.evaluate)


def test_avaliar_localmente_e_resumo():
    def alvo(inputs):
        ferr = ("buscar_logs", "buscar_metricas", "listar_deploys", "comparar_versoes")
        return _resposta(causa="pool de conexões", ferramentas=ferr)

    exemplos = exemplos_dataset()
    linhas = avaliar_localmente(alvo, exemplos[:2])
    assert len(linhas) == 2
    assert linhas[0]["scores"]["causa_certa"] == 1
    assert linhas[0]["scores"]["auditor_aprovou"] is None
    resumo = resumo_metricas(linhas)
    assert resumo["causa_certa"] == 0.5
    assert resumo["auditor_aprovou"] is None


def test_avaliar_localmente_alvo_dict_e_erro():
    def alvo(inputs):
        if inputs["cenario"] == "pool_esgotado":
            raise RuntimeError("falhou")
        return {"causa_principal": "reindex", "ferramentas": []}

    linhas = avaliar_localmente(alvo, exemplos_dataset()[:2])
    assert linhas[0]["erro"] == "falhou" and linhas[0]["scores"]["causa_certa"] == 0
    assert linhas[1]["erro"] is None and linhas[1]["scores"]["causa_certa"] == 1


def test_enviar_ao_langsmith_com_cliente_falso(monkeypatch):
    chamadas = {}

    class Falso:
        def has_dataset(self, dataset_name):
            return False

        def create_dataset(self, nome, **kw):
            chamadas["dataset"] = nome
            return type("D", (), {"id": "1"})()

        def create_examples(self, **kw):
            chamadas["exemplos"] = len(kw["examples"])

    def evaluate_falso(alvo, **kw):
        chamadas["evaluate"] = kw
        return "resultado"

    monkeypatch.setattr(avaliacao, "Client", Falso)
    monkeypatch.setattr(avaliacao, "evaluate", evaluate_falso)
    assert avaliacao.enviar_ao_langsmith(lambda i: {}) == "resultado"
    assert chamadas["dataset"] == "incident-agent-cenarios" and chamadas["exemplos"] == 8
    kw = chamadas["evaluate"]
    assert kw["experiment_prefix"] == "fase5" and kw["max_concurrency"] == 4
    assert len(kw["evaluators"]) == 3
