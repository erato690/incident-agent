"""Moderação com cliente OpenAI falso (sem chave e sem rede)."""
import types

import pytest

from agente import moderacao


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(moderacao, "_avisou", False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def _cliente(flagged=False, categorias=(), erro=None):
    def create(**kw):
        if erro:
            raise erro
        cats = {c: True for c in categorias} | {"outra": False}
        r = types.SimpleNamespace(flagged=flagged, categories=types.SimpleNamespace(model_dump=lambda: cats))
        return types.SimpleNamespace(results=[r])
    return lambda: types.SimpleNamespace(moderations=types.SimpleNamespace(create=create))


def test_sem_chave_pula_sem_excecao():
    r = moderacao.moderar("oi")
    assert r.status == "pulada" and r.motivo


def test_excecao_do_cliente_pula(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(moderacao, "OpenAI", _cliente(erro=RuntimeError("rede")))
    r = moderacao.moderar("oi")
    assert r.status == "pulada" and "rede" in r.motivo


def test_flagged_vira_sinalizada(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(moderacao, "OpenAI", _cliente(True, ["violence", "hate"]))
    r = moderacao.moderar("algo")
    assert r.status == "sinalizada" and r.categorias == ["violence", "hate"]


def test_nao_flagged_vira_ok(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(moderacao, "OpenAI", _cliente(False))
    r = moderacao.moderar("tudo bem")
    assert r.status == "ok" and r.categorias == []


def test_aviso_so_uma_vez(capsys):
    moderacao.moderar("a")
    moderacao.moderar("b")
    assert capsys.readouterr().out.count("Moderação pulada") == 1
