import pytest

from agente import config


@pytest.fixture(autouse=True)
def _sem_env(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    for v in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "FORCAR_PLANO_B"):
        monkeypatch.delenv(v, raising=False)


def test_deepseek_com_chave(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake")
    assert config.escolher_llm().model_name == "deepseek-v4-flash"


def test_plano_b_sem_chave_deepseek(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    assert config.escolher_llm().model_name == "gpt-4o-mini"


def test_forcar_plano_b(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake")
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    monkeypatch.setenv("FORCAR_PLANO_B", "1")
    assert config.escolher_llm().model_name == "gpt-4o-mini"


def test_erro_sem_chaves():
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        config.escolher_llm()


def test_forcar_plano_b_sem_openai(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake")
    monkeypatch.setenv("FORCAR_PLANO_B", "1")
    with pytest.raises(RuntimeError):
        config.escolher_llm()
