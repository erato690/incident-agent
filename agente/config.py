"""Escolha do LLM por provedor (LLM_PROVEDOR), sem troca automática."""

import importlib
import os

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

from agente.rastreamento import desligar_rastreamento_por_padrao

# provedor: (módulo, classe, modelo, variável da chave)
PROVEDORES = {
    "deepseek": ("langchain_deepseek", "ChatDeepSeek", "deepseek-v4-flash", "DEEPSEEK_API_KEY"),
    "openai": ("langchain_openai", "ChatOpenAI", "gpt-4o-mini", "OPENAI_API_KEY"),
}
PADRAO = "openai"


def escolher_llm(provedor: str | None = None) -> BaseChatModel:
    """Provedor = argumento, senão LLM_PROVEDOR, senão openai."""
    load_dotenv()
    desligar_rastreamento_por_padrao()  # LangSmith só onde a seção 5 liga
    nome = (provedor or os.getenv("LLM_PROVEDOR") or PADRAO).strip().lower()
    if nome not in PROVEDORES:
        raise ValueError(f"Provedor inválido: {nome!r}. Opções: {', '.join(PROVEDORES)}.")
    modulo, classe, modelo, var_chave = PROVEDORES[nome]
    if not os.getenv(var_chave):
        raise RuntimeError(f"Defina {var_chave} no .env para usar o provedor {nome}.")
    llm = getattr(importlib.import_module(modulo), classe)(model=modelo, temperature=0)
    print(f"LLM: {nome} · {modelo}")
    return llm


# Só o NLU usa um modelo maior (decisão do Rafael, research.md da Fase 5): o gpt-4o-mini confundia
# "dado faltante" com a causa a investigar. Investigador, Registrador, auditor e sugerir_acao
# continuam no modelo padrão. MODELO_NLU troca o modelo; igual ao padrão, reaproveita o mesmo LLM.
MODELO_NLU_PADRAO = "gpt-4.1"


def llm_do_nlu(llm):
    """LLM do NLU: com OpenAI, o modelo de MODELO_NLU (padrão gpt-4.1); senão, o próprio `llm`."""
    from langchain_openai import ChatOpenAI

    if not isinstance(llm, ChatOpenAI):
        return llm
    modelo = (os.getenv("MODELO_NLU") or MODELO_NLU_PADRAO).strip()
    if modelo == llm.model_name:
        return llm
    return ChatOpenAI(model=modelo, temperature=0)
