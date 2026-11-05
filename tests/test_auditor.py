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
