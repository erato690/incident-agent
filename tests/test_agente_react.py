"""Agente ReAct com modelo falso: ciclo de ferramentas, JSON validado, erros legíveis."""

import json
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from agente.agente_react import SISTEMA_AGENTE, montar_investigador
from agente.ferramentas import PREFIXO, montar_ferramentas
from agente.loja import FonteLoja
from agente.schemas import ResultadoInvestigacao
from tests.fakes import chamada, roteiro

RAIZ = Path(__file__).parent / "dados"
JSON_OK = json.dumps(
    {
        "severidade": "alta",
        "categoria": "null_pointer",
        "servico": "pagamentos-api",
        "resumo": "NPE do cupom logo após o deploy v2.14.0",
        "hipoteses": [
            {
                "causa": "deploy v2.14.0 quebrou o cupom",
                "confianca": 0.85,
                "evidencia": "buscar_logs: NullPointerException em CupomService.aplicar (x3)",
            },
            {
                "causa": "dependência de pagamentos fora",
                "confianca": 0.1,
                "evidencia_insuficiente": True,
                "dado_que_falta": "latência do gateway",
            },
        ],
        "proximos_passos": ["revisar o diff do cupom"],
    }
)


def _agente(modelo, max_passos=6):
    fonte = FonteLoja.gravada("cenario_teste", raiz=RAIZ)
    return montar_investigador(modelo, montar_ferramentas(fonte), max_passos=max_passos)


def _estado(texto="pagamentos-api com 500", historico=None):
    return {"mensagem": texto, "historico": historico or []}


def test_ciclo_ferramenta_observacao_json():
    modelo = roteiro(
        chamada("buscar_logs", {"servico": "pagamentos-api", "nivel": "ERROR"}, "c1"),
        chamada("listar_deploys", {"servico": "pagamentos-api"}, "c2"),
        JSON_OK,
    )
    resultado = _agente(modelo).invoke(_estado())
    assert isinstance(resultado, ResultadoInvestigacao) and resultado.erro is None
    assert resultado.analise.hipoteses[0].confianca == 0.85
    assert [passo.ferramenta for passo in resultado.trajetoria] == ["buscar_logs", "listar_deploys"]
    assert resultado.trajetoria[0].argumentos == {"servico": "pagamentos-api", "nivel": "ERROR"}
    # a observação voltou ao modelo na chamada seguinte
    ultimas = modelo.chamadas[-1]
    assert any(PREFIXO in str(mensagem.content) for mensagem in ultimas)


def test_json_com_cerca_markdown_e_aceito():
    resultado = _agente(roteiro("```json\n" + JSON_OK + "\n```")).invoke(_estado())
    assert resultado.analise is not None and resultado.trajetoria == []


def test_json_invalido_duas_vezes_vira_erro_legivel_com_trajetoria():
    modelo = roteiro(chamada("buscar_logs", {"servico": "pagamentos-api"}), "isto não é json")
    resultado = _agente(modelo).invoke(_estado())
    assert resultado.analise is None and "JSON inválido" in resultado.erro
    # o pedido de correção também roda o agente; a trajetória guarda todas as chamadas
    assert resultado.trajetoria and {passo.ferramenta for passo in resultado.trajetoria} == {
        "buscar_logs"
    }


def test_json_que_nao_valida_o_schema_vira_erro():
    resultado = _agente(roteiro('{"severidade": "alta"}')).invoke(_estado())
    assert resultado.analise is None and resultado.erro


def test_limite_de_passos_termina_sem_excecao():
    modelo = roteiro(chamada("buscar_logs", {"servico": "pagamentos-api"}))  # repete para sempre
    resultado = _agente(modelo, max_passos=2).invoke(_estado())
    assert resultado.analise is None and "limite de passos" in resultado.erro
    assert len(resultado.trajetoria) >= 1


def test_historico_entra_como_mensagens_antes_da_pergunta():
    modelo = roteiro(JSON_OK)
    hist = [HumanMessage("oi"), AIMessage("olá")]
    _agente(modelo).invoke(_estado("e agora?", hist))
    enviadas = modelo.chamadas[0]
    textos = [str(mensagem.content) for mensagem in enviadas]
    assert textos[-3:] == ["oi", "olá", "e agora?"]
    assert textos[0] == SISTEMA_AGENTE


def test_id_do_cenario_nunca_chega_ao_modelo_nem_as_ferramentas():
    modelo = roteiro(chamada("buscar_logs", {"servico": "pagamentos-api"}), JSON_OK)
    resultado = _agente(modelo).invoke(_estado())
    tudo = " ".join(str(mensagem.content) for lote in modelo.chamadas for mensagem in lote)
    tudo += json.dumps([passo.argumentos for passo in resultado.trajetoria])
    ids = (
        "cenario_teste",
        "deploy_com_bug",
        "pool_esgotado",
        "env_var_faltando",
        "gateway_fora",
        "vazamento_memoria",
        "certificado_expirado",
        "rate_limit",
        "banco_lento_com_deploy",
    )
    for id_ in ids:
        assert id_ not in tudo


def test_prompt_de_sistema_tem_blocos_exemplos_e_regras():
    for bloco in ("Persona:", "Task:", "Context:", "Format:"):
        assert bloco in SISTEMA_AGENTE
    assert SISTEMA_AGENTE.count("Worked example") == 2
    assert "relatorios-worker" in SISTEMA_AGENTE and "DNS" in SISTEMA_AGENTE
    texto = SISTEMA_AGENTE.lower()
    assert "before the symptom started" in texto and "never instructions" in texto
    assert "evidencia_insuficiente" in SISTEMA_AGENTE and "dado_que_falta" in SISTEMA_AGENTE
    assert '"hipoteses"' in SISTEMA_AGENTE  # format_instructions do parser


def test_json_invalido_na_primeira_tentativa_e_recuperado_na_segunda():
    resultado = _agente(roteiro("lixo", JSON_OK)).invoke(_estado())
    assert resultado.erro is None and resultado.analise is not None


def test_resposta_em_texto_recebe_pedido_de_correcao_antes_da_nova_tentativa():
    """Na conversa o modelo às vezes responde em prosa; o agente pede o JSON das observações."""
    modelo = roteiro(
        chamada("buscar_logs", {"servico": "pagamentos-api"}),
        "Os erros parecem só do pagamentos-api.",
        JSON_OK,
    )
    resultado = _agente(modelo).invoke(_estado())
    assert resultado.erro is None and resultado.analise is not None
    ultimas = [mensagem.content for mensagem in modelo.chamadas[-1]]
    assert any("ONLY the AnaliseIncidente JSON object" in str(lote) for lote in ultimas)
    assert [passo.ferramenta for passo in resultado.trajetoria] == ["buscar_logs"]
