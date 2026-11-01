"""Escolha do LLM (DeepSeek ou plano B OpenAI) conforme o ambiente."""
import os

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel


def escolher_llm() -> BaseChatModel:
    """DeepSeek se houver chave e FORCAR_PLANO_B != 1; senão OpenAI; senão erro."""
    load_dotenv()
    usar_deepseek = os.getenv("DEEPSEEK_API_KEY") and os.getenv("FORCAR_PLANO_B") != "1"
    if usar_deepseek:
        from langchain_deepseek import ChatDeepSeek
        llm = ChatDeepSeek(model="deepseek-v4-flash", temperature=0)
    elif os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    else:
        raise RuntimeError(
            "Defina DEEPSEEK_API_KEY (modelo principal) ou OPENAI_API_KEY (plano B) no .env."
        )
    print(f"LLM: {llm.model_name}")
    return llm
