import pytest

from agente.loja import ErroLoja, FonteLoja, resumir_estatisticas
from tests.fakes import cliente_http, resposta_json

CENARIOS = [
    "banco_lento_com_deploy",
    "certificado_expirado",
    "deploy_com_bug",
    "env_var_faltando",
    "gateway_fora",
    "pool_esgotado",
    "rate_limit",
    "vazamento_memoria",
]
CAMPOS = {
    "tabela",
    "servicos",
    "varreduras_sequenciais",
    "varreduras_por_indice",
    "reindexacao_em_andamento",
    "operacao_em_andamento",
    "ultimo_analyze",
    "inchaco_indice_pct",
}


def test_ao_vivo_consulta_rota_com_cenario_e_servico():
    pedidos = []
    corpo = {
        "consulta": {"cenario": "pool_esgotado", "servico": "pedidos-api", "momento": "x"},
        "banco": "db-principal",
        "tabelas": [],
    }

    def responder(requisicao):
        pedidos.append(requisicao)
        return resposta_json(corpo)

    fonte = FonteLoja.ao_vivo("http://loja", "pool_esgotado", cliente_http(responder))
    assert fonte.estatisticas_banco("pedidos-api") == corpo
    assert pedidos[0].url.path == "/estatisticas_banco"
    assert dict(pedidos[0].url.params) == {"cenario": "pool_esgotado", "servico": "pedidos-api"}


def test_ao_vivo_servico_invalido_vira_erro_loja():
    fonte = FonteLoja.ao_vivo(
        "http://loja", "pool_esgotado", cliente_http(lambda _: resposta_json({"detail": "x"}, 422))
    )
    with pytest.raises(ErroLoja):
        fonte.estatisticas_banco("outra-api")


@pytest.mark.parametrize("servico", ["pedidos-api", "estoque-worker"])
def test_gravada_filtra_tabelas_do_servico(servico):
    resultado = FonteLoja.gravada("banco_lento_com_deploy").estatisticas_banco(servico)
    assert resultado["consulta"]["servico"] == servico
    assert resultado["consulta"]["cenario"] == "banco_lento_com_deploy"
    assert resultado["banco"] == "db-principal"
    assert all(servico in tabela["servicos"] for tabela in resultado["tabelas"])
    assert "estoque" in {tabela["tabela"] for tabela in resultado["tabelas"]}
    assert set(resultado["tabelas"][0]) == CAMPOS


def test_gravada_estoque_worker_nao_tem_tabelas_do_pedidos():
    tabelas = FonteLoja.gravada("banco_lento_com_deploy").estatisticas_banco("estoque-worker")
    assert {t["tabela"] for t in tabelas["tabelas"]} == {"estoque", "reservas_estoque"}


@pytest.mark.parametrize("servico", ["pagamentos-api", "auth-api"])
def test_gravada_servico_sem_banco_devolve_tabelas_vazias(servico):
    resultado = FonteLoja.gravada("banco_lento_com_deploy").estatisticas_banco(servico)
    assert resultado["tabelas"] == []
    assert resultado["consulta"]["servico"] == servico


def test_gravada_sem_chave_devolve_tabelas_vazias():
    dados = {"cenario": {"id": "x"}}
    resultado = FonteLoja(dados).estatisticas_banco("pedidos-api")
    assert resultado["tabelas"] == [] and resultado["banco"] is None
    assert resultado["consulta"]["servico"] == "pedidos-api"


@pytest.mark.parametrize("cenario", CENARIOS)
def test_fixtures_so_o_banco_lento_tem_manutencao(cenario):
    corpo = FonteLoja.gravada(cenario)._dados["estatisticas_banco"]
    tabelas = corpo["tabelas"]
    operacoes = [t["operacao_em_andamento"] for t in tabelas]
    if cenario == "banco_lento_com_deploy":
        assert any(o and "REINDEX TABLE estoque" in o for o in operacoes)
        assert any(t["reindexacao_em_andamento"] for t in tabelas)
    else:
        assert not any(operacoes) and not any(t["reindexacao_em_andamento"] for t in tabelas)


@pytest.mark.parametrize("servico", ["pedidos-api", "estoque-worker"])
def test_resumo_destaca_reindex(servico):
    resultado = FonteLoja.gravada("banco_lento_com_deploy").estatisticas_banco(servico)
    texto = resumir_estatisticas(resultado)
    assert "MANUTENÇÃO EM ANDAMENTO: REINDEX TABLE estoque na tabela estoque" in texto
    assert "db-principal" in resultado["banco"] and "db-principal" in texto
    assert "2248" in texto and "38" in texto and "41.0" in texto
    assert "2026-10-08T15:47:00-03:00" in texto


def test_resumo_normal_nao_destaca_manutencao():
    texto = resumir_estatisticas(
        FonteLoja.gravada("pool_esgotado").estatisticas_banco("pedidos-api")
    )
    assert "MANUTENÇÃO" not in texto and "pedidos" in texto


def test_resumo_reindexacao_sem_operacao_ainda_destaca():
    tabela = {
        "tabela": "estoque",
        "servicos": ["pedidos-api"],
        "varreduras_sequenciais": 1,
        "varreduras_por_indice": 2,
        "reindexacao_em_andamento": True,
        "operacao_em_andamento": None,
        "ultimo_analyze": "a",
        "inchaco_indice_pct": 3.0,
    }
    resultado = {"consulta": {"servico": "s", "momento": "m"}, "banco": "db-principal"}
    texto = resumir_estatisticas({**resultado, "tabelas": [tabela]})
    assert "MANUTENÇÃO EM ANDAMENTO: REINDEX na tabela estoque" in texto


def test_resumo_sem_tabelas():
    resultado = {"consulta": {"servico": "auth-api"}, "banco": "db-principal", "tabelas": []}
    texto = resumir_estatisticas(resultado)
    assert texto == "Sem estatísticas de banco para auth-api (o serviço não usa o db-principal)."
