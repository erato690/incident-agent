"""Testes do construtor da base SQLite de incidentes (determinística, sem rede)."""

import sqlite3
from pathlib import Path

from agente.loja import TAGS_CONHECIDAS
from scripts.construir_sqlite import construir


def _consulta(caminho: Path, sql: str) -> list[tuple]:
    with sqlite3.connect(caminho) as conexao:
        return conexao.execute(sql).fetchall()


def test_cria_as_tres_tabelas(tmp_path):
    caminho = construir(tmp_path / "i.db")
    tabelas = {
        t for (t,) in _consulta(caminho, "SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"servicos", "deploys", "incidentes"} <= tabelas


def test_quatro_servicos_com_banco_e_dependencia(tmp_path):
    caminho = construir(tmp_path / "i.db")
    nomes = [n for (n,) in _consulta(caminho, "SELECT nome FROM servicos ORDER BY nome")]
    assert nomes == ["auth-api", "estoque-worker", "pagamentos-api", "pedidos-api"]
    dependencia = _consulta(
        caminho, "SELECT dependencia_externa FROM servicos WHERE nome='pagamentos-api'"
    )
    assert dependencia == [("PagaFácil",)]
    bancos = _consulta(
        caminho, "SELECT nome FROM servicos WHERE banco='db-principal' ORDER BY nome"
    )
    assert bancos == [("estoque-worker",), ("pedidos-api",)]


def test_um_deploy_por_tag_conhecida(tmp_path):
    caminho = construir(tmp_path / "i.db")
    tags = {f"{s}/v{v}" for s, v in _consulta(caminho, "SELECT servico, versao FROM deploys")}
    assert tags == set(TAGS_CONHECIDAS)


def test_oito_cenarios_como_incidentes_de_outubro(tmp_path):
    caminho = construir(tmp_path / "i.db")
    linhas = _consulta(
        caminho, "SELECT cenario, inicio FROM incidentes WHERE cenario IS NOT NULL ORDER BY cenario"
    )
    assert len(linhas) == 8
    assert all(inicio.startswith("2026-10") for _, inicio in linhas)


def test_historico_ficticio_jan_a_set_com_pool_em_pedidos_api(tmp_path):
    caminho = construir(tmp_path / "i.db")
    historicos = _consulta(
        caminho, "SELECT inicio FROM incidentes WHERE cenario IS NULL AND inicio < '2026-10'"
    )
    assert len(historicos) >= 14
    pool = _consulta(
        caminho,
        "SELECT COUNT(*) FROM incidentes WHERE servico='pedidos-api' AND categoria='pool_conexoes'",
    )
    assert pool[0][0] >= 2


def test_deterministico_e_reconstrucao_substitui(tmp_path):
    primeiro = construir(tmp_path / "a.db")
    consulta = "SELECT * FROM incidentes ORDER BY id"
    esperado = _consulta(primeiro, consulta)
    construir(primeiro)  # reconstrói sobre o arquivo existente
    assert _consulta(primeiro, consulta) == esperado
    assert _consulta(construir(tmp_path / "b.db"), consulta) == esperado
