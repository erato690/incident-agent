"""Moderação (camada 1) via API gratuita da OpenAI; nunca quebra o fluxo (R4)."""
import os

from openai import OpenAI

from agente.schemas import ResultadoModeracao

_avisou = False


def _pular(motivo: str) -> ResultadoModeracao:
    """Devolve 'pulada' e avisa só na primeira vez da sessão."""
    global _avisou
    if not _avisou:
        _avisou = True
        print(f"Moderação pulada: {motivo}")
    return ResultadoModeracao(status="pulada", motivo=motivo)


def moderar(texto: str) -> ResultadoModeracao:
    """Classifica o texto (já mascarado); sem chave ou com erro, pula."""
    if not os.getenv("OPENAI_API_KEY"):
        return _pular("OPENAI_API_KEY ausente")
    try:
        r = OpenAI().moderations.create(model="omni-moderation-latest", input=texto).results[0]
    except Exception as e:  # qualquer falha de rede ou API
        return _pular(f"erro no cliente: {e}")
    if not r.flagged:
        return ResultadoModeracao(status="ok")
    cats = [c for c, v in r.categories.model_dump().items() if v]
    return ResultadoModeracao(status="sinalizada", categorias=cats)
