"""Moderação com cliente OpenAI falso (sem chave e sem rede)."""

import types

import pytest

from agente import moderacao


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(moderacao, "_avisou", False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def _cliente(flagged=False, categorias=(), erro=None, scores=None):
    """Resposta falsa: categorias marcadas (flag da OpenAI) e category_scores."""
    scores = scores if scores is not None else {categoria: 0.99 for categoria in categorias}

    def create(**opcoes):
        if erro:
            raise erro
        cats = {categoria: True for categoria in categorias} | {"outra": False}
        scores_completos = {"outra": 0.0} | scores
        resultado = types.SimpleNamespace(
            flagged=flagged,
            categories=types.SimpleNamespace(model_dump=lambda **_: cats),
            category_scores=types.SimpleNamespace(model_dump=lambda **_: scores_completos),
        )
        return types.SimpleNamespace(results=[resultado])

    return lambda: types.SimpleNamespace(moderations=types.SimpleNamespace(create=create))


def test_sem_chave_pula_sem_excecao():
    resultado = moderacao.moderar("oi")
    assert resultado.status == "pulada" and resultado.motivo


def test_excecao_do_cliente_pula(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(moderacao, "OpenAI", _cliente(erro=RuntimeError("rede")))
    resultado = moderacao.moderar("oi")
    assert resultado.status == "pulada" and "rede" in resultado.motivo


def test_flagged_vira_sinalizada(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(moderacao, "OpenAI", _cliente(True, ["violence", "hate"]))
    resultado = moderacao.moderar("algo")
    assert resultado.status == "sinalizada" and resultado.categorias == ["violence", "hate"]


def test_oomkilled_violence_abaixo_do_limiar_vira_aviso_e_segue(monkeypatch):
    """Falso positivo de jargão: 'OOMKilled' marca violence ~0.6; abaixo de 0.85 não bloqueia."""
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(moderacao, "OpenAI", _cliente(True, ["violence"], scores={"violence": 0.6}))
    resultado = moderacao.moderar("o container levou OOMKilled")
    assert resultado.status == "aviso"
    assert resultado.categorias == ["violence"] and resultado.scores == {"violence": 0.6}


def test_conteudo_nocivo_acima_do_limiar_bloqueia(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(
        moderacao, "OpenAI", _cliente(True, ["violence"], scores={"violence": 0.95})
    )
    resultado = moderacao.moderar("ameaça real")
    assert resultado.status == "sinalizada" and resultado.categorias == ["violence"]


def test_categoria_sensivel_bloqueia_com_limiar_baixo_mesmo_sem_flag(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(moderacao, "OpenAI", _cliente(False, scores={"self-harm": 0.4}))
    resultado = moderacao.moderar("algo")
    assert resultado.status == "sinalizada" and resultado.categorias == ["self-harm"]


def test_limiares_em_tabela():
    assert moderacao.LIMIARES["violence"] == 0.85
    assert moderacao.LIMIARES["harassment"] == 0.85
    for categoria in ("self-harm", "sexual/minors", "hate/threatening"):
        assert moderacao.LIMIARES[categoria] <= 0.3


def test_nao_flagged_vira_ok(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(moderacao, "OpenAI", _cliente(False))
    resultado = moderacao.moderar("tudo bem")
    assert resultado.status == "ok" and resultado.categorias == []


def test_aviso_so_uma_vez(capsys):
    moderacao.moderar("a")
    moderacao.moderar("b")
    assert capsys.readouterr().out.count("Moderação pulada") == 1
