"""Rastreamento do LangSmith desligado por padrão e ligado só onde a seção 5 pede (sem rede)."""

import logging

import pytest
from langsmith import utils as ls_utils

from agente import rastreamento
from agente.rastreamento import (
    apresentar_cenarios,
    com_rastreamento,
    desligar_rastreamento_por_padrao,
)


@pytest.fixture(autouse=True)
def _sem_rastreamento(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    ls_utils.get_env_var.cache_clear()
    yield
    ls_utils.get_env_var.cache_clear()


def test_padrao_desliga_quando_a_variavel_nao_existe(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    desligar_rastreamento_por_padrao()
    import os

    assert os.environ["LANGSMITH_TRACING"] == "false"


def test_padrao_respeita_quem_definiu_a_variavel(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    desligar_rastreamento_por_padrao()
    import os

    assert os.environ["LANGSMITH_TRACING"] == "true"


def test_escolher_llm_desliga_o_rastreamento(monkeypatch):
    from agente import config

    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        config.escolher_llm("openai")
    import os

    assert os.environ["LANGSMITH_TRACING"] == "false"


def test_liga_so_dentro_do_bloco():
    assert not ls_utils.tracing_is_enabled()
    resultado, aviso = com_rastreamento(lambda: ls_utils.tracing_is_enabled(), esperar=False)
    assert resultado is True and aviso is None
    assert not ls_utils.tracing_is_enabled()


def test_cota_esgotada_vira_aviso_sem_excecao():
    def envio():
        raise ls_utils.LangSmithRateLimitError("429 Too Many Requests: usage limit exceeded")

    resultado, aviso = com_rastreamento(envio, esperar=False)
    assert resultado is None
    assert "LangSmith" in aviso and "429" in aviso


def test_qualquer_falha_do_envio_vira_aviso():
    def envio():
        raise ConnectionError("sem rede")

    resultado, aviso = com_rastreamento(envio, esperar=False)
    assert resultado is None and "ConnectionError" in aviso


def test_aviso_do_envio_em_segundo_plano_vira_aviso():
    """O envio dos traces roda em outra thread e só registra no log; a célula mostra o aviso."""

    def turno():
        logging.getLogger("langsmith.client").warning("Failed to batch ingest runs: 429 quota")
        return "ok"

    resultado, aviso = com_rastreamento(turno, esperar=False)
    assert resultado == "ok"
    assert aviso and "429" in aviso


def test_espera_o_envio_dos_traces(monkeypatch):
    esperou = []
    monkeypatch.setattr(rastreamento, "_esperar_envio", lambda: esperou.append(True))
    com_rastreamento(lambda: 1)
    assert esperou == [True]


def test_apresentacao_roda_uma_vez_por_cenario_e_segue_apos_falha():
    vistos = []

    def rodar(cenario):
        vistos.append((cenario, ls_utils.tracing_is_enabled()))
        if cenario == "b":
            raise RuntimeError("modelo fora")
        return f"resposta de {cenario}"

    linhas, aviso = apresentar_cenarios(rodar, ["a", "b", "c"], esperar=False)
    assert vistos == [("a", True), ("b", True), ("c", True)]
    assert [linha["cenario"] for linha in linhas] == ["a", "b", "c"]
    assert linhas[0]["resultado"] == "resposta de a" and linhas[0]["erro"] is None
    assert linhas[1]["resultado"] is None and "RuntimeError" in linhas[1]["erro"]
    assert aviso is None
    assert not ls_utils.tracing_is_enabled()


def _script(monkeypatch):
    import importlib.util
    from pathlib import Path

    caminho = Path(__file__).resolve().parent.parent / "scripts" / "avaliar_langsmith.py"
    especificacao = importlib.util.spec_from_file_location("avaliar_langsmith", caminho)
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    monkeypatch.setattr(modulo, "load_dotenv", lambda: None)
    monkeypatch.setattr(modulo, "montar_alvo", lambda: lambda inputs: {})
    monkeypatch.setattr(rastreamento, "_esperar_envio", lambda: None)
    return modulo


def test_script_envia_com_rastreamento_ligado_so_no_envio(monkeypatch, capsys):
    modulo = _script(monkeypatch)
    vistos = []

    def enviar(alvo, prefixo):
        vistos.append((prefixo, ls_utils.tracing_is_enabled()))
        return type("Experimento", (), {"experiment_name": "fase5-abc"})()

    monkeypatch.setattr(modulo, "enviar_ao_langsmith", enviar)
    modulo.main(["--enviar"])
    assert vistos == [("fase5", True)]
    assert "fase5-abc" in capsys.readouterr().out
    assert not ls_utils.tracing_is_enabled()


def test_script_com_cota_esgotada_avisa_e_termina_sem_erro(monkeypatch, capsys):
    modulo = _script(monkeypatch)

    def enviar(alvo, prefixo):
        raise ls_utils.LangSmithRateLimitError("429 monthly usage limit")

    monkeypatch.setattr(modulo, "enviar_ao_langsmith", enviar)
    modulo.main(["--enviar"])
    saida = capsys.readouterr().out
    assert "LangSmith indisponível" in saida and "429" in saida


def test_script_local_nao_rastreia(monkeypatch, capsys):
    modulo = _script(monkeypatch)
    vistos = []

    def avaliar(alvo, exemplos):
        vistos.append(ls_utils.tracing_is_enabled())
        return []

    monkeypatch.setattr(modulo, "avaliar_localmente", avaliar)
    modulo.main([])
    assert vistos == [False]
