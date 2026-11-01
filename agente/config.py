"""Escolha do LLM por provedor (LLM_PROVEDOR), sem troca automática."""
import importlib
import os

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

# provedor: (módulo, classe, modelo, variável da chave)
PROVEDORES = {
    "deepseek": ("langchain_deepseek", "ChatDeepSeek", "deepseek-v4-flash", "DEEPSEEK_API_KEY"),
    "openai": ("langchain_openai", "ChatOpenAI", "gpt-4o-mini", "OPENAI_API_KEY"),
}
PADRAO = "openai"


def escolher_llm(provedor: str | None = None) -> BaseChatModel:
    """Provedor = argumento, senão LLM_PROVEDOR, senão openai."""
    load_dotenv()
    nome = (provedor or os.getenv("LLM_PROVEDOR") or PADRAO).strip().lower()
    if nome not in PROVEDORES:
        raise ValueError(f"Provedor inválido: {nome!r}. Opções: {', '.join(PROVEDORES)}.")
    modulo, classe, modelo, var_chave = PROVEDORES[nome]
    if not os.getenv(var_chave):
        raise RuntimeError(f"Defina {var_chave} no .env para usar o provedor {nome}.")
    llm = getattr(importlib.import_module(modulo), classe)(model=modelo, temperature=0)
    print(f"LLM: {nome} · {modelo}")
    return llm
