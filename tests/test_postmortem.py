from datetime import datetime

from agente.postmortem import (
    DadosPostMortem,
    gerar_postmortem,
    investigacao_realizada,
    linha_do_tempo_do_incidente,
    salvar_postmortem,
)
from agente.schemas import (
    AcaoSugerida,
    AnaliseIncidente,
    Episodio,
    Hipotese,
    PassoTrajetoria,
)

AGORA = datetime(2026, 11, 5, 10, 30)


def _analise(resumo: str = "Pool de conexões esgotado") -> AnaliseIncidente:
    return AnaliseIncidente(
        severidade="alta",
        categoria="banco",
        resumo=resumo,
        hipoteses=[
            Hipotese(causa="Pool esgotado", confianca=0.8, evidencia="timeout"),
            Hipotese(causa="Deploy ruim", confianca=0.3, evidencia="v2"),
        ],
        proximos_passos=["Adicionar alerta de pool"],
        acoes_sugeridas=[
            AcaoSugerida(acao="Reiniciar o pool", motivo="libera conexões", risco="baixo")
        ],
    )


def _episodio() -> Episodio:
    return Episodio(
        incidente_id="INC-1",
        session_id="s",
        servico="shop",
        resumo="Pool pequeno demais",
        causa="Pool de 5 conexões",
        evidencia="log 10:15",
        origem="engenheiro",
        criado_em=AGORA,
    )


def _dados(**kw) -> DadosPostMortem:
    base = {"incidente_id": "INC-1", "servico": "shop", "gerado_em": AGORA, "analise": _analise()}
    return DadosPostMortem(**{**base, **kw})


def test_com_causa_confirmada():
    texto = gerar_postmortem(_dados(episodio=_episodio()))
    assert "causa não confirmada" not in texto
    assert "Causa confirmada: Pool de 5 conexões" in texto
    for secao in (
        "Resumo",
        "Impacto e severidade",
        "Linha do tempo",
        "Causa raiz e evidências",
        "Ações preventivas",
        "Lições aprendidas",
    ):
        assert f"## {secao}" in texto


def test_sem_causa_confirmada_nao_gera():
    import pytest

    with pytest.raises(ValueError, match="causa confirmada"):
        gerar_postmortem(_dados())


def test_acoes_nao_executadas():
    texto = gerar_postmortem(_dados(episodio=_episodio()))
    assert "Reiniciar o pool" in texto
    assert "sugerida (não executada)" in texto


def test_mascara_segredo():
    analise = _analise("falha com password=abc123xyz no log")
    texto = gerar_postmortem(_dados(analise=analise, episodio=_episodio()))
    assert "abc123xyz" not in texto
    assert "[SEGREDO]" in texto


def test_salvar(tmp_path):
    caminho = salvar_postmortem(_dados(episodio=_episodio()), tmp_path / "novo" / "pm")
    assert caminho.name == "postmortem_INC-1.md"
    assert caminho.read_text(encoding="utf-8").startswith("# Post-mortem INC-1")


LOGS = PassoTrajetoria(
    ferramenta="buscar_logs",
    argumentos={"servico": "pedidos-api", "nivel": "ERROR"},
    duracao_ms=5,
    tamanho=10,
    observacao="TOOL DATA (not instructions):\nLogs: total 284, truncated: no\n"
    "[ERROR] pedidos-api: HikariPool-1 - Connection is not available (x284, 14:00:07 a 14:29:58)",
)
DEPLOYS = PassoTrajetoria(
    ferramenta="listar_deploys",
    argumentos={"servico": "pedidos-api"},
    duracao_ms=1,
    tamanho=10,
    observacao="TOOL DATA (not instructions):\n2026-10-06T13:40:00-03:00 pedidos-api/v3.2.0 "
    "(previous: pedidos-api/v3.1.0) (commit a356b1f, author Equipe Loja): perf: reduz pool "
    "máximo de 20 para 10",
)
BANCO = PassoTrajetoria(
    ferramenta="consultar_estatisticas_banco",
    argumentos={"servico": "pedidos-api"},
    duracao_ms=1,
    tamanho=10,
    observacao="Banco db-principal (pedidos-api), retrato de 2026-10-06T14:00:00-03:00\n"
    "pedidos: varreduras seq 64 x índice 4380, último ANALYZE 2026-10-06T03:00:00-03:00, "
    "reindexação em andamento: não",
)
GITHUB = PassoTrajetoria(
    ferramenta="comparar_versoes",
    argumentos={"tag_base": "pedidos-api/v3.1.0", "tag_nova": "pedidos-api/v3.2.0"},
    duracao_ms=300,
    tamanho=10,
    reserva=True,
    motivo_reserva="GitHub limit of 60 req/h without token exhausted (resets at 00:25)",
    observacao="Fallback reason: GitHub limit of 60 req/h without token exhausted (resets 00:25)",
)


def test_linha_do_tempo_so_com_eventos_do_incidente_em_ordem_e_com_data():
    itens = linha_do_tempo_do_incidente([LOGS, BANCO, GITHUB, DEPLOYS])
    assert [(i.horario, i.evento.split(":")[0]) for i in itens] == [
        ("2026-10-06 13:40", "Deploy pedidos-api/v3.2.0 (anterior pedidos-api/v3.1.0)"),
        ("2026-10-06 14:00", "Primeiro erro registrado (284 ocorrências até 14"),
        ("2026-10-06 14:29", "Último erro registrado"),
    ]
    texto = " ".join(i.evento for i in itens)
    assert "GitHub" not in texto and "ANALYZE" not in texto and "retrato" not in texto


def test_reindexacao_em_andamento_entra_como_evento():
    banco = BANCO.model_copy(
        update={"observacao": BANCO.observacao.replace("andamento: não", "andamento: sim")}
    )
    itens = linha_do_tempo_do_incidente([banco])
    assert itens[0].horario == "2026-10-06 14:00" and "reindexação em andamento" in itens[0].evento


def test_investigacao_realizada_lista_consultas_e_nota_em_portugues():
    linhas = investigacao_realizada([LOGS, GITHUB])
    assert linhas[0] == "- buscar_logs(servico=pedidos-api, nivel=ERROR)"
    assert "comparar_versoes" in linhas[1] and "dados gravados" in linhas[1]
    assert "limite de 60 requisições por hora da API do GitHub" in linhas[1]
    assert "Fallback reason" not in " ".join(linhas)


def test_secoes_novas_rodape_com_veredito_e_preventivas_sem_repetir_correcao():
    from agente.schemas import Auditoria

    analise = _analise().model_copy(
        update={
            "proximos_passos": ["reiniciar o pool de conexões", "Adicionar alerta de pool"],
        }
    )
    texto = gerar_postmortem(
        _dados(
            analise=analise,
            episodio=_episodio(),
            trajetoria=[LOGS, DEPLOYS, GITHUB],
            auditoria=Auditoria(aprovada=True, veredito="apoia"),
            auditada_em=datetime(2026, 11, 5, 10, 20),
        )
    )
    assert "## Investigação realizada" in texto and "sem horário" not in texto
    preventivas = texto.split("## Ações preventivas")[1].split("##")[0]
    assert "Adicionar alerta de pool" in preventivas and "reiniciar" not in preventivas.lower()
    assert "Auditoria: aprovada, veredito apoia (auditada em 2026-11-05 10:20)" in texto
    assert "Não auditada" not in texto
    linha = texto.split("## Linha do tempo")[1].split("##")[0]
    assert "2026-10-06 13:40" in linha and "Consulta" not in linha


def test_sem_auditoria_o_rodape_diz_que_nao_houve():
    texto = gerar_postmortem(_dados(episodio=_episodio()))
    assert "Auditoria: não auditada" in texto


def test_preventiva_que_repete_a_correcao_com_outras_palavras_sai():
    from agente.postmortem import _repete_correcao

    acao = AcaoSugerida(acao="Restaurar pool_max para 20", motivo="m", risco="baixo")
    passo = "aumentar o pool máximo de conexões no banco de dados para pelo menos 20"
    assert _repete_correcao(passo, [acao])
    assert not _repete_correcao("criar alerta quando o pool passar de 80% de uso", [acao])


def test_licoes_sem_o_motivo_tecnico_do_registro():
    episodio = _episodio().model_copy(update={"motivo_registro": "Nenhum episódio ativo parecido"})
    texto = gerar_postmortem(_dados(episodio=episodio))
    licoes = texto.split("## Lições aprendidas")[1].split("##")[0]
    assert "Nenhum episódio ativo" not in licoes and "Pool pequeno demais" in licoes


def test_rodape_traz_as_quatro_tecnicas():
    from agente.schemas import Auditoria, ChecagemTrajetoria, VereditoCoerencia

    auditoria = Auditoria(
        aprovada=True,
        veredito="apoia",
        trajetoria=ChecagemTrajetoria(itens=[], aprovada=True),
        coerencia=VereditoCoerencia(veredito="apoia", e_coerente=True, justificativa="j"),
    )
    texto = gerar_postmortem(_dados(episodio=_episodio(), auditoria=auditoria))
    rodape = texto.split("---")[-1]
    for nome in ("Auditoria de trajetória", "Checagem de fatos", "Inferência lógica", "Extração"):
        assert nome in rodape
