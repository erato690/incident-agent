"""FonteLoja (gravada e ao vivo, contrato 1.0.0) e resumos de logs, métricas e deploys."""

import json
from pathlib import Path

import httpx
import pytest

from agente.loja import (
    ErroLoja,
    FonteLoja,
    fonte_padrao,
    resumir_deploys,
    resumir_logs,
    resumir_metricas,
)

RAIZ = Path(__file__).parent / "dados"
DADOS = json.loads((RAIZ / "cenario_teste.json").read_text(encoding="utf-8"))


@pytest.fixture
def fonte():
    return FonteLoja.gravada("cenario_teste", raiz=RAIZ)


def test_logs_filtra_por_servico_e_traz_total(fonte):
    resultado = fonte.logs("pagamentos-api")
    assert resultado["total"] == 5 and resultado["truncado"] is False
    assert {registro["servico"] for registro in resultado["logs"]} == {"pagamentos-api"}


def test_logs_filtra_por_nivel_sem_diferenciar_caixa(fonte):
    assert fonte.logs("pagamentos-api", nivel="error")["total"] == 3


def test_metricas_e_deploys_filtrados(fonte):
    assert len(fonte.metricas("pagamentos-api")) == 2
    assert [serie["metrica"] for serie in fonte.metricas("pagamentos-api", "erros_5xx")] == [
        "erros_5xx"
    ]
    assert [deploy["tag"] for deploy in fonte.deploys("pagamentos-api")] == [
        "pagamentos-api/v2.14.0"
    ]
    assert len(fonte.deploys()) == 2


def test_metrica_desconhecida_na_gravada_e_erro_legivel(fonte):
    with pytest.raises(ErroLoja, match="Unknown metric"):
        fonte.metricas("pagamentos-api", "Erros5xx")


def test_cenario_inexistente_levanta_erro_legivel():
    with pytest.raises(FileNotFoundError, match="inexistente"):
        FonteLoja.gravada("inexistente", raiz=RAIZ)


def _loja_falsa(chamadas, erro=None):
    def tratar(requisicao: httpx.Request) -> httpx.Response:
        chamadas.append(requisicao)
        if erro:
            return httpx.Response(erro, json={"detail": "Cenário desconhecido: x"})
        rota = requisicao.url.path
        if rota == "/logs":
            return httpx.Response(
                200, json={"total": 5, "truncado": False, "logs": DADOS["logs"]["logs"][:2]}
            )
        if rota == "/metricas":
            return httpx.Response(200, json={"series": DADOS["metricas"]["series"][:1]})
        return httpx.Response(200, json={"deploys": DADOS["deploys"]["deploys"]})

    return httpx.Client(transport=httpx.MockTransport(tratar))


def test_ao_vivo_logs_envia_cenario_servico_nivel_e_limite():
    chamadas = []
    fonte_ao_vivo = FonteLoja.ao_vivo(
        "http://loja/", "pool_esgotado", cliente=_loja_falsa(chamadas)
    )
    resultado = fonte_ao_vivo.logs("pedidos-api", "error")
    parametros = dict(chamadas[0].url.params)
    assert chamadas[0].url.path == "/logs" and chamadas[0].method == "GET"
    assert parametros == {
        "cenario": "pool_esgotado",
        "servico": "pedidos-api",
        "nivel": "ERROR",
        "limite": "500",
    }
    assert resultado["total"] == 5 and len(resultado["logs"]) == 2


def test_ao_vivo_metricas_e_deploys_enviam_so_o_que_o_contrato_pede():
    chamadas = []
    fonte_ao_vivo = FonteLoja.ao_vivo("http://loja", "gateway_fora", cliente=_loja_falsa(chamadas))
    assert fonte_ao_vivo.metricas("pagamentos-api", "erros_5xx")[0]["metrica"] == "erros_5xx"
    assert len(fonte_ao_vivo.deploys()) == 2
    assert dict(chamadas[0].url.params) == {
        "cenario": "gateway_fora",
        "servico": "pagamentos-api",
        "metrica": "erros_5xx",
    }
    assert dict(chamadas[1].url.params) == {"cenario": "gateway_fora"}


def test_ao_vivo_cenario_vem_da_fonte_nunca_do_modelo():
    chamadas = []
    fonte_ao_vivo = FonteLoja.ao_vivo("http://loja", "rate_limit", cliente=_loja_falsa(chamadas))
    fonte_ao_vivo.logs("auth-api")
    assert chamadas[0].url.params["cenario"] == "rate_limit"
    with pytest.raises(TypeError):
        fonte_ao_vivo.logs("auth-api", cenario="pool_esgotado")


@pytest.mark.parametrize("status", [404, 422])
def test_ao_vivo_404_e_422_viram_erro_legivel(status):
    fonte_ao_vivo = FonteLoja.ao_vivo("http://loja", "x", cliente=_loja_falsa([], erro=status))
    with pytest.raises(ErroLoja, match=f"{status}.*desconhecido"):
        fonte_ao_vivo.deploys()


def test_ao_vivo_falha_de_rede_vira_erro_legivel():
    def cai(requisicao):
        raise httpx.ConnectTimeout("tempo esgotado")

    fonte_ao_vivo = FonteLoja.ao_vivo(
        "http://loja", "x", cliente=httpx.Client(transport=httpx.MockTransport(cai))
    )
    with pytest.raises(ErroLoja, match="unavailable"):
        fonte_ao_vivo.logs("auth-api")


def test_fonte_padrao_escolhe_pela_variavel_loja_url(monkeypatch):
    monkeypatch.delenv("LOJA_URL", raising=False)
    assert fonte_padrao("cenario_teste", raiz=RAIZ)._url is None
    monkeypatch.setenv("LOJA_URL", "http://loja:9/")
    fonte_ao_vivo = fonte_padrao("cenario_teste", raiz=RAIZ)
    assert fonte_ao_vivo._url == "http://loja:9" and fonte_ao_vivo.cenario == "cenario_teste"


def test_resumo_logs_agrupa_conta_e_mostra_total(fonte):
    texto = resumir_logs(fonte.logs("pagamentos-api", nivel="ERROR"))
    assert "total 3" in texto and "truncated: no" in texto
    assert "x3" in texto and "NullPointerException" in texto
    assert "14:08:01" in texto and "14:09:30" in texto


def test_resumo_logs_avisa_quando_truncado():
    resultado = {"total": 900, "truncado": True, "logs": DADOS["logs"]["logs"][:1]}
    assert "total 900" in resumir_logs(resultado) and "truncated: yes" in resumir_logs(resultado)


def test_resumo_logs_limita_grupos(fonte):
    texto = resumir_logs(fonte.logs("pagamentos-api"), max_grupos=2)
    assert texto.count("\n") + 1 <= 4  # cabeçalho + 2 grupos + linha de omitidos (omitted)
    assert "omitted" in texto


def test_resumo_logs_vazio(fonte):
    assert "no logs" in resumir_logs(fonte.logs("auth-api")).lower()


def test_resumo_metricas_usa_resumo_e_unidade(fonte):
    texto = resumir_metricas(fonte.metricas("pagamentos-api", "erros_5xx"))
    assert "erros_5xx (erros/min)" in texto
    assert "min 0.2" in texto and "max 44.5" in texto and "last 44.5" in texto and "avg" in texto
    assert "no metrics" in resumir_metricas([]).lower()


def test_resumo_deploys(fonte):
    texto = resumir_deploys(fonte.deploys("pagamentos-api"))
    for esperado in ("2026-10-01T14:05:00", "pagamentos-api/v2.14.0", "a1b2c3d", "ana", "cupom"):
        assert esperado in texto
    assert "no deploys" in resumir_deploys([]).lower()


def test_resumo_deploys_informa_a_tag_anterior_do_mesmo_servico(fonte):
    tags = fonte.tags_do_servico()
    texto = resumir_deploys(fonte.deploys("pagamentos-api"), tags)
    assert "pagamentos-api/v2.14.0 (previous: pagamentos-api/v2.13.4)" in texto
    primeira = {"horario": "h", "tag": "pedidos-api/v3.1.0", "commit": "c", "autor": "a"}
    assert "previous" not in resumir_deploys([{**primeira, "mensagem": "m"}], tags)


def test_ao_vivo_tags_usam_deploys_sem_janela_e_ordenam_por_horario():
    chamadas = []
    corpo = {
        "deploys": [
            {"horario": "2026-10-08T15:45:00-03:00", "tag": "pedidos-api/v3.2.1"},
            {"horario": "2026-10-06T13:40:00-03:00", "tag": "pedidos-api/v3.2.0"},
        ]
    }

    def tratar(requisicao):
        chamadas.append(requisicao)
        return httpx.Response(200, json=corpo)

    cliente = httpx.Client(transport=httpx.MockTransport(tratar))
    fonte_ao_vivo = FonteLoja.ao_vivo("http://loja", "pool_esgotado", cliente=cliente)
    assert fonte_ao_vivo.tags_do_servico() == ["pedidos-api/v3.2.0", "pedidos-api/v3.2.1"]
    assert dict(chamadas[0].url.params) == {}


def test_resumir_logs_agrupa_mensagens_que_so_diferem_nos_numeros():
    logs = [
        {
            "horario": f"2026-10-27T11:5{indice}:00-03:00",
            "servico": "auth-api",
            "nivel": "WARN",
            "mensagem": f"GC overhead alto: heap usado {85 + indice}%",
        }
        for indice in range(6)
    ]
    texto = resumir_logs({"total": 6, "truncado": False, "logs": logs})
    assert texto.count("GC overhead alto") == 1 and "x6" in texto
    assert "90%" in texto  # mostra o exemplo mais recente


def test_resumir_logs_prioriza_erros_quando_omite_grupos():
    logs = [
        {
            "horario": f"2026-10-27T11:{indice:02d}:00-03:00",
            "servico": "auth-api",
            "nivel": "INFO",
            "mensagem": f"rota /r{chr(97 + indice)} ok",
        }
        for indice in range(10)
    ]
    logs.append(
        {
            "horario": "2026-10-27T12:05:00-03:00",
            "servico": "auth-api",
            "nivel": "ERROR",
            "mensagem": "container auth-api OOMKilled",
        }
    )
    texto = resumir_logs({"total": 11, "truncado": False, "logs": logs}, max_grupos=3)
    assert "OOMKilled" in texto and "groups omitted" in texto
