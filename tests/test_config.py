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


def test_nlu_usa_modelo_maior_e_o_resto_fica_no_padrao(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-teste")
    monkeypatch.delenv("MODELO_NLU", raising=False)
    llm = config.escolher_llm("openai")
    nlu = config.llm_do_nlu(llm)
    assert llm.model_name == "gpt-4o-mini" and nlu.model_name == config.MODELO_NLU_PADRAO
    assert config.MODELO_NLU_PADRAO == "gpt-4.1" and nlu.temperature == 0


def test_modelo_nlu_configuravel_e_igual_ao_padrao_reaproveita(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-teste")
    llm = config.escolher_llm("openai")
    monkeypatch.setenv("MODELO_NLU", "gpt-4o")
    assert config.llm_do_nlu(llm).model_name == "gpt-4o"
    monkeypatch.setenv("MODELO_NLU", "gpt-4o-mini")
    assert config.llm_do_nlu(llm) is llm


def test_nlu_com_outro_provedor_ou_falso_nao_troca(monkeypatch):
    falso = object()
    assert config.llm_do_nlu(falso) is falso
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-teste")
    deepseek = config.escolher_llm("deepseek")
    assert config.llm_do_nlu(deepseek) is deepseek
