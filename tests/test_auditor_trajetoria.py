"""Quarta técnica do auditor: auditoria de trajetória (determinística), e tolerância numérica
na checagem de fatos."""

from agente.auditor import (
    TOLERANCIA_NUMERO,
    auditar_trajetoria,
    checar_fatos,
    resumo_tecnicas,
)
from agente.schemas import Afirmacao, AnaliseIncidente, Auditoria, Hipotese, PassoTrajetoria
from tests.test_auditor import CERTAS, LlmFalso, _audita


def _passo(ferramenta, argumentos=None, observacao=""):
    return PassoTrajetoria(
        ferramenta=ferramenta,
        argumentos=argumentos or {},
        duracao_ms=1,
        tamanho=1,
        observacao=observacao,
    )


DEPLOYS = _passo(
    "listar_deploys",
    {"servico": "pedidos-api"},
    "2026-10-06T13:40:00-03:00 pedidos-api/v3.2.0 (previous: pedidos-api/v3.1.0): reduz pool",
)
LOGS = _passo("buscar_logs", {"servico": "pedidos-api", "nivel": "ERROR"}, "timeout (x284)")
DIFF = _passo(
    "comparar_versoes", {"tag_base": "pedidos-api/v3.1.0", "tag_nova": "pedidos-api/v3.2.0"}
)


def _analise(causa, evidencia):
    return AnaliseIncidente(
        severidade="alta",
        categoria="pool",
        servico="pedidos-api",
        resumo="r",
        hipoteses=[
            Hipotese(causa=causa, confianca=0.9, evidencia=evidencia),
            Hipotese(causa="outra", confianca=0.1, evidencia="e"),
        ],
        proximos_passos=["p"],
    )


CERTA = _analise(
    "a v3.2.0 reduziu o pool_max de 20 para 10",
    "listar_deploys: v3.2.0 às 13:40; comparar_versoes: pool_max 20 para 10; buscar_logs: x284",
)


def _status(checagem, criterio):
    return next(i.status for i in checagem.itens if i.criterio == criterio)


def test_trajetoria_certa_passa_nos_quatro_criterios():
    checagem = auditar_trajetoria(CERTA, [LOGS, DEPLOYS, DIFF], "pedidos-api com timeout")
    assert checagem.aprovada
    assert {i.criterio for i in checagem.itens} == {
        "fontes_citadas",
        "argumentos",
        "ferramentas_minimas",
        "sem_escrita",
    }
    assert all(i.status == "ok" for i in checagem.itens)


def test_ferramenta_citada_e_nao_chamada_e_grave():
    checagem = auditar_trajetoria(CERTA, [LOGS, DEPLOYS], "x")
    assert _status(checagem, "fontes_citadas") == "grave" and not checagem.aprovada


def test_versao_citada_fora_dos_deploys_listados_e_grave():
    errada = _analise("o deploy v9.9.9 causou a regressão", "listar_deploys mostra v9.9.9 às 16:30")
    checagem = auditar_trajetoria(errada, [LOGS, DEPLOYS], "x")
    assert _status(checagem, "argumentos") == "grave" and not checagem.aprovada


def test_argumento_de_outro_servico_e_tags_fora_dos_deploys_sao_falha_leve():
    outro = _passo("buscar_metricas", {"servico": "auth-api"})
    tags = _passo(
        "comparar_versoes", {"tag_base": "pedidos-api/v1.0.0", "tag_nova": "pedidos-api/v3.2.0"}
    )
    checagem = auditar_trajetoria(CERTA, [LOGS, DEPLOYS, DIFF, outro, tags], "pedidos-api lento")
    assert _status(checagem, "argumentos") == "falha" and checagem.aprovada


def test_culpar_deploy_sem_listar_deploys_e_grave_e_sem_diff_e_falha():
    sem_deploys = _analise("a v3.2.0 reduziu o pool", "buscar_logs: x284")
    assert _status(auditar_trajetoria(sem_deploys, [LOGS], "x"), "ferramentas_minimas") == "grave"
    sem_diff = _analise("a v3.2.0 reduziu o pool", "listar_deploys: v3.2.0; buscar_logs: x284")
    checagem = auditar_trajetoria(sem_diff, [LOGS, DEPLOYS], "x")
    assert _status(checagem, "ferramentas_minimas") == "falha" and checagem.aprovada


def test_sem_logs_e_grave_e_chamada_repetida_a_toa_e_falha():
    so_deploys = _analise("REINDEX em andamento", "consultar_estatisticas_banco: REINDEX")
    banco = _passo("consultar_estatisticas_banco", {"servico": "pedidos-api"})
    assert _status(auditar_trajetoria(so_deploys, [banco], "x"), "ferramentas_minimas") == "grave"
    repetidas = [LOGS, LOGS, LOGS, banco]
    assert _status(auditar_trajetoria(so_deploys, repetidas, "x"), "ferramentas_minimas") == "falha"


def test_ferramenta_de_escrita_na_investigacao_e_grave():
    escrita = _passo("gravar_episodio", {"causa": "x"})
    checagem = auditar_trajetoria(CERTA, [LOGS, DEPLOYS, DIFF, escrita], "x")
    assert _status(checagem, "sem_escrita") == "grave" and not checagem.aprovada


def test_trajetoria_sem_ferramentas_conhecidas_nao_se_aplica():
    checagem = auditar_trajetoria(CERTA, [_passo("f")], "x")
    assert _status(checagem, "ferramentas_minimas") == "nao_se_aplica"


def test_auditor_reprova_com_trajetoria_grave_e_expoe_a_checagem():
    escrita = [LOGS, _passo("gravar_fato")]
    auditoria = _audita(LlmFalso(CERTAS), trajetoria=escrita)
    assert auditoria.trajetoria is not None and not auditoria.trajetoria.aprovada
    assert not auditoria.aprovada
    assert any("trajetória" in m for m in auditoria.motivos)


def test_tolerancia_numerica_em_contagens_e_percentuais():
    assert TOLERANCIA_NUMERO == 0.05
    fonte = [_passo("buscar_logs", observacao="timeout (x284); erros 37,5%")]

    def status(valor):
        return checar_fatos([Afirmacao(texto="t", chave="numero", valor=valor)], fonte)[0]

    assert status("284").status == "confirmada"
    proximo = status("280")
    assert proximo.status == "confirmada" and "tolerância" in proximo.fonte
    assert status("38%").status == "confirmada"
    assert status("300").status == "nao_verificada"  # 5,6% acima
    assert status("5").status == "nao_verificada"  # número pequeno: só casamento exato


def test_resumo_das_quatro_tecnicas():
    auditoria = _audita(LlmFalso(CERTAS))
    tecnicas = resumo_tecnicas(auditoria)
    assert [t["tecnica"] for t in tecnicas] == [
        "Auditoria de trajetória",
        "Checagem de fatos determinística",
        "Inferência lógica (NLI)",
        "Extração com Pydantic",
    ]
    assert all(t["status"] in {"ok", "falha", "nao_se_aplica"} for t in tecnicas)
    assert resumo_tecnicas(Auditoria(aprovada=False)) == []


def test_tolerancia_respeita_a_unidade_percentual():
    fonte = [_passo("buscar_metricas", observacao="req/min max 36.2; erros 12,0%")]

    def status(valor):
        return checar_fatos([Afirmacao(texto="t", chave="numero", valor=valor)], fonte)[0].status

    assert status("37%") == "nao_verificada"  # 36.2 não é percentual
    assert status("12,4%") == "confirmada"
    assert status("37") == "confirmada"
