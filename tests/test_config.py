import pytest

from agente import config


@pytest.fixture(autouse=True)
def _sem_env(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda *args, **kwargs: None)
    for variavel in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_PROVEDOR"):
        monkeypatch.delenv(variavel, raising=False)


def test_padrao_openai_sem_llm_provedor(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    assert config.escolher_llm().model_name == "gpt-4o-mini"


def test_env_deepseek(monkeypatch):
    monkeypatch.setenv("LLM_PROVEDOR", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake")
    assert config.escolher_llm().model_name == "deepseek-v4-flash"


def test_argumento_sobrepoe_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVEDOR", "openai")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake")
    assert config.escolher_llm("deepseek").model_name == "deepseek-v4-flash"


def test_valor_invalido_lista_opcoes():
    with pytest.raises(ValueError, match="deepseek.*openai|openai.*deepseek"):
        config.escolher_llm("gemini")


def test_chave_ausente_cita_variavel():
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        config.escolher_llm()
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        config.escolher_llm("deepseek")


def test_sem_troca_automatica(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        config.escolher_llm()


def test_normaliza_maiusculas_e_espacos(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake")
    assert config.escolher_llm("DeepSeek ").model_name == "deepseek-v4-flash"


def test_imprime_provedor_e_modelo(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    config.escolher_llm()
    assert "LLM: openai · gpt-4o-mini" in capsys.readouterr().out
