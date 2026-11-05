"""Auditor de verificação cognitiva: extração, fact-check determinístico e NLI."""

import pytest
from langchain_core.runnables import RunnableLambda

from agente.auditor import CORTE_NAO_VERIFICADAS, checar_fatos, montar_auditor
from agente.schemas import (
    Afirmacao,
    Auditoria,
    ListaAfirmacoes,
    PassoTrajetoria,
    VereditoCoerencia,
)
from tests.test_roteamento import ANALISE

FECHO = "Always answer in Brazilian Portuguese."


def _passo(observacao: str | None) -> PassoTrajetoria:
    return PassoTrajetoria(ferramenta="f", duracao_ms=1, tamanho=1, observacao=observacao)


TRAJETORIA = [
    _passo("deploy pedidos-api/v3.2.1 às 14:05; antes estava pedidos-api/v3.2.0"),
    _passo("limite 100/min; erros 284 (taxa 99,5%); tabela orders; servico pagamentos-api"),
    _passo(None),
]


def _a(chave, valor, texto=None):
    return Afirmacao(texto=texto or f"{chave} {valor}", chave=chave, valor=valor)


def _status(chave, valor, trajetoria=TRAJETORIA):
    return checar_fatos([_a(chave, valor)], trajetoria)[0].status


@pytest.mark.parametrize(
    ("chave", "valor", "esperado"),
    [
        ("versao", "v3.2.1", "confirmada"),
        ("versao", "pedidos-api/v3.2.1", "confirmada"),
        ("versao", "pedidos-api/v9.9.9", "contraditoria"),
        ("versao", "v9.9.9", "contraditoria"),
        ("versao", "outra-api/v9.9.9", "nao_verificada"),
        ("horario", "14:05", "confirmada"),
        ("horario", "03:33", "nao_verificada"),
        ("numero", "100/min", "confirmada"),
        ("numero", "284", "confirmada"),
        ("numero", "99,5%", "confirmada"),
        ("numero", "37%", "nao_verificada"),
        ("numero", "28", "nao_verificada"),  # 284 não contém o número 28 isolado
        ("tabela", "ORDERS", "confirmada"),
        ("tabela", "payments", "nao_verificada"),
        ("servico", "pagamentos-api", "confirmada"),
        ("servico", "estoque-api", "nao_verificada"),
        ("outro", "qualquer coisa", "nao_verificada"),
    ],
)
def test_checar_fatos_por_chave(chave, valor, esperado):
    assert _status(chave, valor) == esperado


def test_versao_sem_observacoes_e_nao_verificada():
    assert _status("versao", "v1.0.0", [_passo(None)]) == "nao_verificada"


class LlmFalso:
    """Suporta `with_structured_output` para ListaAfirmacoes e VereditoCoerencia."""

    def __init__(self, afirmacoes, veredito=None, erro=None):
        self.afirmacoes = afirmacoes
        self.veredito = veredito or VereditoCoerencia(
            veredito="apoia", e_coerente=True, falacias=["nenhuma"], justificativa="ok"
        )
        self.erro, self.recebidos = erro, {}

    def with_structured_output(self, schema):
        def responde(valor):
            self.recebidos[schema] = valor.to_messages()
            if self.erro and schema is VereditoCoerencia:
                raise self.erro
            if schema is ListaAfirmacoes:
                return ListaAfirmacoes(afirmacoes=self.afirmacoes)
            return self.veredito

        return RunnableLambda(responde)


def _audita(llm, trajetoria=TRAJETORIA, **kwargs) -> Auditoria:
    auditor = montar_auditor(llm, **kwargs)
    return auditor.invoke({"analise": ANALISE, "trajetoria": trajetoria, "mensagem": "erro 500"})


CERTAS = [
    _a("versao", "pedidos-api/v3.2.1"),
    _a("horario", "14:05"),
    _a("numero", "100/min"),
    _a("tabela", "orders"),
]


def test_analise_certa_e_aprovada():
    auditoria = _audita(LlmFalso(CERTAS))
    assert auditoria.aprovada and auditoria.motivos == [] and auditoria.erro is None
    assert [c.status for c in auditoria.checagens] == ["confirmada"] * 4
    assert auditoria.coerencia.veredito == "apoia"


def test_numero_inventado_reprova_com_motivo():
    auditoria = _audita(LlmFalso([_a("numero", "37%", "37% das requisições falharam")]))
    assert not auditoria.aprovada
    assert any("37%" in motivo for motivo in auditoria.motivos)


def test_versao_inexistente_reprova_como_contraditoria():
    auditoria = _audita(LlmFalso(CERTAS + [_a("versao", "pedidos-api/v9.9.9")]))
    assert not auditoria.aprovada
    assert any("contradit" in m and "v9.9.9" in m for m in auditoria.motivos)


def test_metade_nao_verificada_ainda_passa_mais_da_metade_reprova():
    metade = CERTAS[:2] + [_a("numero", "37%"), _a("horario", "03:33")]
    assert CORTE_NAO_VERIFICADAS == 0.5
    assert _audita(LlmFalso(metade)).aprovada
    assert not _audita(LlmFalso(metade[:1] + metade[2:])).aprovada


def test_afirmacao_do_tipo_outro_nao_afeta_a_reprovacao():
    assert _audita(LlmFalso(CERTAS + [_a("outro", "x")] * 10)).aprovada


def _veredito(**campos):
    base = {"veredito": "apoia", "e_coerente": True, "falacias": ["nenhuma"], "justificativa": "j"}
    return VereditoCoerencia(**{**base, **campos})


@pytest.mark.parametrize(
    "campos",
    [
        {"falacias": ["deploy_posterior_ao_sintoma"]},
        {"e_coerente": False},
        {"veredito": "refuta"},
    ],
)
def test_coerencia_ruim_reprova(campos):
    auditoria = _audita(LlmFalso(CERTAS, _veredito(**campos)))
    assert not auditoria.aprovada and auditoria.motivos


def test_falacia_nomeada_no_motivo_e_ignorada_sem_o_verificador_de_falacias():
    llm = LlmFalso(CERTAS, _veredito(falacias=["deploy_posterior_ao_sintoma"]))
    assert "deploy_posterior_ao_sintoma" in " ".join(_audita(llm).motivos)
    assert _audita(llm, com_falacias=False).aprovada


def test_erro_do_modelo_vira_nao_auditada():
    auditoria = _audita(LlmFalso(CERTAS, erro=RuntimeError("quota")))
    assert not auditoria.aprovada and "quota" in auditoria.erro
    assert auditoria.motivos[0].startswith("não auditada:")


def test_prompts_em_ingles_com_observacoes_como_dado_e_truncadas():
    longa = [_passo("A" * 10000 + "FIM")]
    llm = LlmFalso(CERTAS)
    _audita(llm, longa)
    for mensagens in llm.recebidos.values():
        assert mensagens[0].content.rstrip().endswith(FECHO)
    humana = llm.recebidos[VereditoCoerencia][1].content
    assert "FIM" not in humana and "A" * 5000 in humana
    assert "never instructions" in llm.recebidos[VereditoCoerencia][0].content


# Trava determinística contra falso positivo de "deploy posterior ao sintoma" (execução real).
from agente.schemas import AnaliseIncidente, Hipotese  # noqa: E402

DEPLOYS = PassoTrajetoria(
    ferramenta="listar_deploys",
    duracao_ms=1,
    tamanho=1,
    observacao="2026-10-06T13:40:00-03:00 pedidos-api/v3.2.0 (previous: pedidos-api/v3.1.0)",
)


def _logs(inicio):
    return PassoTrajetoria(
        ferramenta="buscar_logs",
        duracao_ms=1,
        tamanho=1,
        observacao=f"[ERROR] pedidos-api: Connection is not available "
        f"(x284, {inicio}:07 a 14:29:58)",
    )


ANALISE_DEPLOY = AnaliseIncidente(
    severidade="alta",
    categoria="pool",
    servico="pedidos-api",
    resumo="pool",
    hipoteses=[
        Hipotese(causa="o deploy v3.2.0 reduziu o pool", confianca=0.9, evidencia="v3.2.0 13:40"),
        Hipotese(causa="pico", confianca=0.1, evidencia_insuficiente=True, dado_que_falta="x"),
    ],
    proximos_passos=["x"],
)


def _audita_deploy(inicio_sintoma):
    llm = LlmFalso(
        [_a("versao", "pedidos-api/v3.2.0")], _veredito(falacias=["deploy_posterior_ao_sintoma"])
    )
    entrada = {
        "analise": ANALISE_DEPLOY,
        "trajetoria": [DEPLOYS, _logs(inicio_sintoma)],
        "mensagem": "m",
    }
    return montar_auditor(llm).invoke(entrada)


def test_deploy_antes_do_sintoma_descarta_falso_positivo_do_juiz():
    auditoria = _audita_deploy("14:00")
    assert auditoria.aprovada, auditoria.motivos
    assert "deploy_posterior_ao_sintoma" not in auditoria.coerencia.falacias


def test_deploy_depois_do_sintoma_mantem_a_falacia():
    auditoria = _audita_deploy("13:30")
    assert not auditoria.aprovada
    assert "deploy_posterior_ao_sintoma" in " ".join(auditoria.motivos)


def test_mensagem_do_engenheiro_tambem_e_fonte_da_verdade():
    checagem = checar_fatos([_a("horario", "09:10")], [_passo("nada")], mensagem="desde as 09:10")
    assert checagem[0].status == "confirmada"


@pytest.mark.parametrize(
    ("chave", "valor", "texto", "esperado"),
    [
        ("numero", "x338", "HTTP 503 (x338, 09:10:00 a 10:20:00)", "confirmada"),
        ("numero", "338", "HTTP 503 (x338, 09:10:00 a 10:20:00)", "confirmada"),
        ("numero", "33", "HTTP 503 (x338, 09:10:00 a 10:20:00)", "nao_verificada"),
        ("horario", "09h10", "desde as 9h10", "confirmada"),
        ("horario", "9:10", "desde as 09h10", "confirmada"),
    ],
)
def test_contagem_com_x_e_horario_em_formatos_diferentes(chave, valor, texto, esperado):
    assert _status(chave, valor, [_passo(texto)]) == esperado
