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
    "varreduras_sequenciais",
    "varreduras_por_indice",
    "linhas_vivas",
    "linhas_mortas",
    "ultimo_analyze",
    "ultimo_vacuum",
    "inchaco_indices_pct",
    "bloqueios_aguardando",
    "manutencao_em_andamento",
}


def test_ao_vivo_consulta_rota_com_cenario_e_servico():
    pedidos = []
    corpo = {"cenario": "pool_esgotado", "servico": "pedidos-api", "banco": "db-principal"}

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


def test_gravada_filtra_por_servico():
    fonte = FonteLoja.gravada("banco_lento_com_deploy")
    resultado = fonte.estatisticas_banco("estoque-worker")
    assert resultado["servico"] == "estoque-worker"
    assert resultado["banco"] == "db-principal"
    assert {tabela["tabela"] for tabela in resultado["tabelas"]} >= {"estoque"}
    assert set(resultado["tabelas"][0]) == CAMPOS


def test_gravada_servico_sem_banco_devolve_tabelas_vazias():
    resultado = FonteLoja.gravada("certificado_expirado").estatisticas_banco("auth-api")
    assert resultado == {
        "cenario": "certificado_expirado",
        "servico": "auth-api",
        "banco": None,
        "coletado_em": None,
        "tabelas": [],
    }


def test_gravada_sem_chave_devolve_tabelas_vazias():
    dados = {"cenario": {"id": "x"}}
    assert FonteLoja(dados).estatisticas_banco("pedidos-api")["tabelas"] == []


@pytest.mark.parametrize("cenario", CENARIOS)
def test_fixtures_so_o_banco_lento_tem_manutencao(cenario):
    dados = FonteLoja.gravada(cenario)._dados["estatisticas_banco"]
    manutencoes = [t["manutencao_em_andamento"] for item in dados for t in item["tabelas"]]
    assert all(item["servico"] != "auth-api" for item in dados)
    if cenario == "banco_lento_com_deploy":
        assert any(m and "REINDEX TABLE estoque" in m for m in manutencoes)
    else:
        assert not any(manutencoes)


def test_resumo_destaca_reindex():
    resultado = FonteLoja.gravada("banco_lento_com_deploy").estatisticas_banco("pedidos-api")
    texto = resumir_estatisticas(resultado)
    assert "MANUTENÇÃO EM ANDAMENTO: REINDEX TABLE estoque (iniciado 15:44)" in texto
    assert "37" in texto and "estoque" in texto and "db-principal" in texto


def test_resumo_normal_nao_destaca_manutencao():
    texto = resumir_estatisticas(
        FonteLoja.gravada("pool_esgotado").estatisticas_banco("pedidos-api")
    )
    assert "MANUTENÇÃO" not in texto and "pedidos" in texto


def test_resumo_sem_tabelas():
    resultado = {"servico": "auth-api", "tabelas": []}
    assert resumir_estatisticas(resultado) == "Sem estatísticas de banco para auth-api."
