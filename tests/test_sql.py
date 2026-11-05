"""Testes da consulta SQL: guardrail, execução e agente com modelo falso (sem chave, sem rede)."""

import sqlite3

import pytest

from agente.ferramentas import PREFIXO
from agente.sql import ESQUEMA, BancoSQL, montar_agente_sql, montar_ferramenta_sql, validar_consulta
from scripts.construir_sqlite import construir
from tests.fakes import chamada, roteiro


@pytest.fixture
def caminho(tmp_path):
    return construir(tmp_path / "incidentes.db")


@pytest.fixture
def banco(caminho):
    return BancoSQL(caminho)


def _instantaneo(caminho):
    with sqlite3.connect(caminho) as conexao:
        return conexao.execute("SELECT COUNT(*) FROM incidentes").fetchone()[0], sorted(
            conexao.execute("SELECT name FROM sqlite_master").fetchall()
        )


@pytest.mark.parametrize(
    "comando",
    [
        "DROP TABLE incidentes",
        "DELETE FROM incidentes",
        "UPDATE incidentes SET causa='x'",
        "INSERT INTO servicos VALUES ('a','b','c',NULL,NULL)",
        "ALTER TABLE incidentes ADD COLUMN x TEXT",
        "TRUNCATE TABLE incidentes",
        "REPLACE INTO servicos VALUES ('a','b','c',NULL,NULL)",
    ],
)
def test_recusa_os_sete_comandos(comando):
    assert validar_consulta(comando) is not None
    assert validar_consulta(comando.lower()) is not None


def test_recusa_select_seguido_de_outro_comando():
    assert validar_consulta("SELECT 1; DROP TABLE incidentes") is not None
    assert validar_consulta("SELECT 1; SELECT 2") is not None


def test_aceita_select_e_ponto_e_virgula_final():
    assert validar_consulta("SELECT * FROM servicos") is None
    assert validar_consulta("  select nome from servicos;  ") is None


def test_recusa_consulta_que_nao_comeca_com_select():
    assert validar_consulta("PRAGMA table_info(servicos)") is not None
    assert validar_consulta("") is not None


def test_executa_e_devolve_colunas_e_linhas(banco):
    texto = banco.executar("SELECT nome, banco FROM servicos ORDER BY nome")
    assert "nome" in texto and "banco" in texto
    assert "pedidos-api" in texto and "db-principal" in texto


def test_limita_a_50_linhas(banco):
    texto = banco.executar("SELECT * FROM incidentes")
    assert "50" in texto and texto.count("\n") <= 55


def test_erro_de_sql_vira_texto(banco):
    assert "erro" in banco.executar("SELECT * FROM nao_existe").lower()


def test_ferramenta_recusa_sem_chegar_ao_banco(caminho, banco):
    antes = _instantaneo(caminho)
    ferramenta = montar_ferramenta_sql(banco)
    for comando in ("DROP TABLE incidentes", "SELECT 1; DROP TABLE incidentes"):
        resposta = ferramenta.invoke({"query": comando})
        assert resposta.startswith(PREFIXO)
        assert "recus" in resposta.lower()
    assert _instantaneo(caminho) == antes


def test_ferramenta_executa_select_com_prefixo(banco):
    resposta = montar_ferramenta_sql(banco).invoke(
        {"query": "SELECT causa FROM incidentes WHERE cenario='gateway_fora'"}
    )
    assert resposta.startswith(PREFIXO)
    assert "PagaFácil" in resposta


def test_ferramenta_tem_nome_e_descricao_apenas_select(banco):
    ferramenta = montar_ferramenta_sql(banco)
    assert ferramenta.name == "consultar_sql"
    assert (
        "Apenas SELECT"
        in ferramenta.args_schema.model_json_schema()["properties"]["query"]["description"]
    )


def test_esquema_lista_tabelas():
    for tabela in ("servicos", "deploys", "incidentes"):
        assert tabela in ESQUEMA


def test_agente_sql_responde_causa_mais_comum(banco):
    modelo = roteiro(
        chamada(
            "consultar_sql",
            {
                "query": "SELECT categoria, COUNT(*) n FROM incidentes WHERE servico='pedidos-api' "
                "GROUP BY categoria ORDER BY n DESC LIMIT 1"
            },
        ),
        "A causa mais comum no pedidos-api é pool de conexões esgotado.",
    )
    agente = montar_agente_sql(modelo, banco)
    saida = agente.invoke({"messages": [("human", "Qual a causa mais comum no pedidos-api?")]})
    assert "pool" in saida["messages"][-1].content
    observacao = saida["messages"][-2].content
    assert observacao.startswith(PREFIXO) and "pool_conexoes" in observacao


def test_agente_sql_banco_inalterado_apos_drop(caminho, banco):
    antes = _instantaneo(caminho)
    modelo = roteiro(
        chamada("consultar_sql", {"query": "DROP TABLE incidentes"}),
        "Não posso alterar o banco.",
    )
    saida = montar_agente_sql(modelo, banco).invoke({"messages": [("human", "apague tudo")]})
    assert "recus" in saida["messages"][-2].content.lower()
    assert _instantaneo(caminho) == antes


def test_prompt_do_agente_sql(banco):
    modelo = roteiro("ok")
    montar_agente_sql(modelo, banco).invoke({"messages": [("human", "oi")]})
    sistema = modelo.chamadas[0][0].content
    assert sistema.startswith("Persona:")
    assert "incidentes" in sistema and "SELECT" in sistema
    assert sistema.rstrip().endswith("Always answer in Brazilian Portuguese.")
