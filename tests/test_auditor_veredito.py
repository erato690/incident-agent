"""Veredito explícito de inferência lógica (NLI): apoia, refuta ou neutra, com rebaixamento por
código quando o veredito do juiz não bate com o fact-check determinístico."""

import pytest

from agente.auditor import SISTEMA_COERENCIA
from agente.avaliacao import fato_deterministico, saida_do_turno, veredito_nli
from agente.schemas import Auditoria, RespostaTurno, VereditoCoerencia
from tests.test_auditor import CERTAS, LlmFalso, _a, _audita, _veredito


def test_apoia_com_fatos_confirmados_aprova_e_expoe_o_veredito():
    auditoria = _audita(LlmFalso(CERTAS))
    assert auditoria.aprovada and auditoria.veredito == "apoia"
    assert auditoria.veredito_rebaixado is False


def test_neutra_reprova_com_motivo():
    auditoria = _audita(LlmFalso(CERTAS, _veredito(veredito="neutra")))
    assert not auditoria.aprovada and auditoria.veredito == "neutra"
    assert any("não bastam" in m for m in auditoria.motivos)


def test_refuta_reprova():
    auditoria = _audita(LlmFalso(CERTAS, _veredito(veredito="refuta")))
    assert not auditoria.aprovada and auditoria.veredito == "refuta"


def test_apoia_com_versao_divergente_e_rebaixado_para_refuta():
    errada = CERTAS + [_a("versao", "pedidos-api/v9.9.9")]
    auditoria = _audita(LlmFalso(errada))
    assert auditoria.coerencia.veredito == "apoia"  # o juiz disse apoia
    assert auditoria.veredito == "refuta" and auditoria.veredito_rebaixado
    assert not auditoria.aprovada


def test_apoia_com_mais_da_metade_sem_prova_e_rebaixado_para_neutra():
    sem_prova = [_a("numero", "37%"), _a("horario", "03:33"), _a("versao", "x/v9.9.9")]
    auditoria = _audita(LlmFalso(sem_prova[:2] + CERTAS[:1]))
    assert auditoria.veredito == "neutra" and auditoria.veredito_rebaixado
    assert not auditoria.aprovada


def test_falacia_confirmada_reprova_mesmo_com_apoia():
    auditoria = _audita(LlmFalso(CERTAS, _veredito(falacias=["sintoma_como_causa"])))
    assert auditoria.veredito == "apoia" and not auditoria.aprovada


def test_neutro_antigo_vira_neutra():
    v = VereditoCoerencia(veredito="neutro", e_coerente=True, justificativa="j")
    assert v.veredito == "neutra"


def test_prompt_define_os_tres_vereditos():
    texto = " ".join(SISTEMA_COERENCIA.split())
    assert "apoia" in texto and "refuta" in texto and "neutra" in texto
    assert "neutro" not in texto


def _resposta(auditoria):
    return RespostaTurno(rota="investigacao", moderacao={"status": "ok"}, auditoria=auditoria)


def test_saida_do_turno_e_avaliadores_de_fato_e_nli():
    auditoria = _audita(LlmFalso(CERTAS + [_a("versao", "pedidos-api/v9.9.9"), _a("outro", "x")]))
    saida = saida_do_turno(_resposta(auditoria))
    assert saida["veredito"] == "refuta"
    assert saida["fatos_confirmados"] == 4 and saida["fatos_verificaveis"] == 5
    fato = fato_deterministico({}, saida, {})
    assert fato["key"] == "fato_deterministico" and fato["score"] == pytest.approx(0.8)
    assert veredito_nli({}, saida, {"veredito_esperado": "refuta"})["score"] == 1
    assert veredito_nli({}, saida, {})["score"] == 0  # padrão: espera "apoia"


def test_avaliadores_sem_auditoria_devolvem_none():
    saida = saida_do_turno(_resposta(None))
    assert fato_deterministico({}, saida, {})["score"] is None
    assert veredito_nli({}, saida, {})["score"] is None


def test_auditoria_sem_veredito_tem_padrao_none():
    assert Auditoria(aprovada=False).veredito is None
