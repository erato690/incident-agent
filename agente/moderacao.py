"""Moderação (camada 1) via API gratuita da OpenAI; nunca quebra o fluxo (R4)."""
import os

from openai import OpenAI

from agente.schemas import ResultadoModeracao

_avisou = False

# Limiar de bloqueio por categoria (category_scores de 0 a 1). Jargão técnico ("OOMKilled",
# "kill -9", "matar o processo") puxa violence/harassment para cima sem ser nocivo, então essas
# categorias só bloqueiam com score alto. Categorias graves bloqueiam com score baixo.
LIMIARES = {
    "violence": 0.85, "violence/graphic": 0.85,
    "harassment": 0.85, "harassment/threatening": 0.6,
    "hate": 0.6, "hate/threatening": 0.3,
    "illicit": 0.85, "illicit/violent": 0.6,
    "sexual": 0.6, "sexual/minors": 0.1,
    "self-harm": 0.3, "self-harm/intent": 0.3, "self-harm/instructions": 0.3,
}
LIMIAR_PADRAO = 0.5  # categoria nova que ainda não está na tabela


def _pular(motivo: str) -> ResultadoModeracao:
    """Devolve 'pulada' e avisa só na primeira vez da sessão."""
    global _avisou
    if not _avisou:
        _avisou = True
        print(f"Moderação pulada: {motivo}")
    return ResultadoModeracao(status="pulada", motivo=motivo)


def moderar(texto: str) -> ResultadoModeracao:
    """Classifica o texto (já mascarado) com limiar por categoria; sem chave ou com erro, pula."""
    if not os.getenv("OPENAI_API_KEY"):
        return _pular("OPENAI_API_KEY ausente")
    try:
        r = OpenAI().moderations.create(model="omni-moderation-latest", input=texto).results[0]
    except Exception as e:  # qualquer falha de rede ou API
        return _pular(f"erro no cliente: {e}")
    scores = r.category_scores.model_dump(by_alias=True)
    bloqueadas = [c for c, s in scores.items() if s >= LIMIARES.get(c, LIMIAR_PADRAO)]
    if bloqueadas:
        return ResultadoModeracao(status="sinalizada", categorias=bloqueadas,
                                  scores={c: scores[c] for c in bloqueadas})
    if r.flagged:  # a OpenAI marcou, mas abaixo do nosso limiar: registra e segue
        marcadas = [c for c, v in r.categories.model_dump(by_alias=True).items() if v]
        return ResultadoModeracao(status="aviso", categorias=marcadas,
                                  scores={c: scores.get(c, 0.0) for c in marcadas})
    return ResultadoModeracao(status="ok")
