"""comparar_versoes: API do GitHub (transporte falso), reserva gravada e resumo."""

import json
from pathlib import Path

import httpx
import pytest

from agente.github import (
    MARCA_RESERVA,
    ComparacaoVersoes,
    ErroComparacao,
    comparar_versoes,
    nome_reserva,
    resumir_comparacao,
)
from tests.fakes import cliente_http, resposta_json

BASE, NOVA = "pagamentos-api/v2.13.4", "pagamentos-api/v2.14.0"
API = {
    "total_commits": 1,
    "commits": [
        {
            "commit": {
                "message": "feat: cupom\n\ncorpo longo",
                "author": {"name": "ana", "email": "ana@x.com", "date": "2026-10-14T17:20:00Z"},
            }
        }
    ],
    "files": [
        {
            "filename": "src/Pagamento.java",
            "status": "modified",
            "additions": 1,
            "deletions": 1,
            "patch": "@@ -1 +1 @@\n-desconto(c)\n+desconto(c.getValor())" + "x" * 3000,
        }
    ],
}


def _reserva(tmp_path: Path) -> Path:
    (tmp_path / nome_reserva(BASE, NOVA)).write_text(json.dumps(API), encoding="utf-8")
    return tmp_path


def test_nome_reserva_troca_barra():
    assert nome_reserva(BASE, NOVA) == "pagamentos-api__v2.13.4...pagamentos-api__v2.14.0.json"


def test_url_usa_barra_literal_e_resume(tmp_path):
    vistas = []

    def resp(requisicao: httpx.Request):
        vistas.append(requisicao)
        return resposta_json(API)

    comparacao = comparar_versoes(BASE, NOVA, cliente_http(resp), raiz_reserva=tmp_path)
    assert str(vistas[0].url) == (
        "https://api.github.com/repos/erato690/incident-shop/compare/"
        "pagamentos-api/v2.13.4...pagamentos-api/v2.14.0"
    )
    assert isinstance(comparacao, ComparacaoVersoes) and comparacao.reserva is False
    assert comparacao.commits[0].mensagem == "feat: cupom" and comparacao.commits[0].autor == "ana"
    assert "email" not in comparacao.commits[0].model_dump()
    assert (
        comparacao.arquivos[0].nome == "src/Pagamento.java"
        and len(comparacao.arquivos[0].trecho) <= 800
    )


def test_token_opcional_no_cabecalho(tmp_path, monkeypatch):
    vistas = []
    cliente = cliente_http(lambda requisicao: (vistas.append(requisicao), resposta_json(API))[1])
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    comparar_versoes(BASE, NOVA, cliente, raiz_reserva=tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "t0k")
    comparar_versoes(BASE, NOVA, cliente, raiz_reserva=tmp_path)
    assert "authorization" not in vistas[0].headers
    assert vistas[1].headers["authorization"] == "Bearer t0k"


@pytest.mark.parametrize(
    "falha",
    [
        lambda requisicao: httpx.Response(403),
        lambda requisicao: httpx.Response(429),
        lambda requisicao: (_ for _ in ()).throw(httpx.ConnectError("sem rede")),
    ],
)
def test_erros_usam_reserva(tmp_path, falha):
    comparacao = comparar_versoes(BASE, NOVA, cliente_http(falha), raiz_reserva=_reserva(tmp_path))
    assert comparacao.reserva is True and len(comparacao.commits) == 1
    assert MARCA_RESERVA in resumir_comparacao(comparacao)


def test_motivo_do_limite_de_requisicoes_aparece_no_resumo(tmp_path):
    cabecalhos = {
        "x-ratelimit-limit": "60",
        "x-ratelimit-remaining": "0",
        "x-ratelimit-reset": "1793573929",
    }
    cliente = cliente_http(lambda requisicao: httpx.Response(403, headers=cabecalhos))
    comparacao = comparar_versoes(BASE, NOVA, cliente, raiz_reserva=_reserva(tmp_path))
    motivo = comparacao.motivo_reserva
    assert "GitHub limit of 60 req/h without token exhausted" in motivo
    assert "x-ratelimit-remaining=0, resets at " in motivo
    assert f"Fallback reason: {motivo}" in resumir_comparacao(comparacao)


def test_motivo_sem_rede_e_outros_status(tmp_path):
    def sem_rede(requisicao):
        raise httpx.ConnectError("sem rede")

    comparacao = comparar_versoes(
        BASE, NOVA, cliente_http(sem_rede), raiz_reserva=_reserva(tmp_path)
    )
    assert comparacao.motivo_reserva.startswith("no network: ConnectError")
    comparacao = comparar_versoes(
        BASE,
        NOVA,
        cliente_http(lambda requisicao: httpx.Response(500)),
        raiz_reserva=_reserva(tmp_path),
    )
    assert comparacao.motivo_reserva == "GitHub responded 500"


def test_erro_sem_reserva_vira_erro_legivel(tmp_path):
    with pytest.raises(ErroComparacao, match="recorded fallback"):
        comparar_versoes(
            BASE, NOVA, cliente_http(lambda requisicao: httpx.Response(429)), raiz_reserva=tmp_path
        )


def test_404_vira_erro_legivel_sem_reserva(tmp_path):
    with pytest.raises(ErroComparacao, match="not found"):
        comparar_versoes(
            BASE,
            NOVA,
            cliente_http(lambda requisicao: httpx.Response(404)),
            raiz_reserva=_reserva(tmp_path),
        )


def test_resumo_traz_commits_arquivos_e_trecho(tmp_path):
    comparacao = comparar_versoes(
        BASE, NOVA, cliente_http(lambda requisicao: resposta_json(API)), raiz_reserva=tmp_path
    )
    texto = resumir_comparacao(comparacao)
    assert (
        "feat: cupom" in texto
        and "src/Pagamento.java" in texto
        and "+desconto(c.getValor())" in texto
    )
    assert MARCA_RESERVA not in texto
