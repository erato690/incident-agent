"""Avaliação do agente: dataset de cenários, avaliadores e envio ao LangSmith (F5-D2 A).

Os avaliadores seguem o formato do `langsmith.evaluate` (0.14): recebem
`(inputs, outputs, reference_outputs)` e devolvem `{"key", "score", "comment"}`.
"""

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from langsmith import Client, evaluate

from agente.schemas import RespostaTurno

RAIZ = Path(__file__).resolve().parent.parent
FERRAMENTAS_PROIBIDAS: list[str] = []
EXTRAS_FERRAMENTAS = {
    "banco_lento_com_deploy": ["consultar_estatisticas_banco"],
    "rate_limit": ["consultar_wiki"],
}


def exemplos_dataset() -> list[dict]:
    """Os itens com `palavras_causa` da bateria da Fase 4, no formato de exemplo do LangSmith."""
    fase4 = json.loads((RAIZ / "dados_dummy/fase4_mensagens.json").read_text(encoding="utf-8"))
    fase2 = json.loads((RAIZ / "dados_dummy/fase2_mensagens.json").read_text(encoding="utf-8"))
    esperadas = {
        m["cenario"]: m["ferramentas_esperadas"]
        for m in reversed(fase2)  # os itens de investigação vêm antes dos de barreira
        if m.get("ferramentas_esperadas")
    }
    exemplos = []
    for item in fase4:
        if not item.get("palavras_causa"):
            continue
        cenario = item["cenario"]
        ferramentas = esperadas.get(cenario, []) + EXTRAS_FERRAMENTAS.get(cenario, [])
        exemplos.append(
            {
                "inputs": {"mensagem": item["mensagem"], "cenario": cenario},
                "outputs": {
                    "palavras_causa": item["palavras_causa"],
                    "causa_esperada": item["causa_esperada"],
                    "ferramentas_esperadas": ferramentas,
                },
            }
        )
    return exemplos


def saida_do_turno(resposta: RespostaTurno) -> dict:
    """Saída serializável de um turno, usada pelos avaliadores."""
    principal = None
    if resposta.analise is not None and resposta.analise.hipoteses:
        principal = max(resposta.analise.hipoteses, key=lambda h: h.confianca)
    auditoria = getattr(resposta, "auditoria", None)
    return {
        "rota": resposta.rota,
        "causa_principal": principal.causa if principal else None,
        "confianca": principal.confianca if principal else None,
        "ferramentas": [passo.ferramenta for passo in resposta.trajetoria],
        "auditoria_aprovada": getattr(auditoria, "aprovada", None),
        "aviso": getattr(resposta, "aviso", None),
    }


def causa_certa(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    causa = (outputs.get("causa_principal") or "").casefold()
    palavras = reference_outputs.get("palavras_causa") or []
    acertou = any(p.casefold() in causa for p in palavras)
    return {"key": "causa_certa", "score": int(acertou), "comment": causa or "sem causa"}


def trajetoria_ferramentas(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    chamadas = set(outputs.get("ferramentas") or [])
    esperadas = reference_outputs.get("ferramentas_esperadas") or []
    proibidas = chamadas & set(FERRAMENTAS_PROIBIDAS)
    if proibidas:
        return {
            "key": "trajetoria_ferramentas",
            "score": 0,
            "comment": f"proibida: {sorted(proibidas)}",
        }
    faltantes = [f for f in esperadas if f not in chamadas]
    score = 1.0 if not esperadas else (len(esperadas) - len(faltantes)) / len(esperadas)
    comment = f"faltaram: {faltantes}" if faltantes else "todas chamadas"
    return {"key": "trajetoria_ferramentas", "score": score, "comment": comment}


def auditor_aprovou(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    aprovada = outputs.get("auditoria_aprovada")
    score = None if aprovada is None else int(bool(aprovada))
    return {"key": "auditor_aprovou", "score": score, "comment": outputs.get("aviso") or ""}


AVALIADORES: list[Callable[..., dict]] = [causa_certa, trajetoria_ferramentas, auditor_aprovou]


def _como_saida(retorno: Any) -> dict:
    return saida_do_turno(retorno) if isinstance(retorno, RespostaTurno) else dict(retorno)


def _avaliar_exemplo(alvo: Callable, exemplo: dict) -> dict:
    erro, saida = None, {}
    try:
        saida = _como_saida(alvo(exemplo["inputs"]))
    except Exception as exc:  # noqa: BLE001 - o erro do alvo vira linha avaliada
        erro = str(exc)
    scores = {}
    for avaliador in AVALIADORES:
        r = avaliador(exemplo["inputs"], saida, exemplo["outputs"])
        scores[r["key"]] = r["score"]
    return {"inputs": exemplo["inputs"], "outputs": saida, "scores": scores, "erro": erro}


def avaliar_localmente(alvo: Callable, exemplos: list[dict], max_workers: int = 4) -> list[dict]:
    """Roda o alvo em cada exemplo e aplica os avaliadores, sem rede."""
    with ThreadPoolExecutor(max_workers) as pool:
        return list(pool.map(lambda e: _avaliar_exemplo(alvo, e), exemplos))


def resumo_metricas(linhas: list[dict]) -> dict[str, float | None]:
    """Média de cada métrica, ignorando os scores None (None se nenhum valor)."""
    chaves = [a.__name__ for a in AVALIADORES]
    resumo: dict[str, float | None] = {}
    for chave in chaves:
        valores = [x["scores"][chave] for x in linhas if x["scores"].get(chave) is not None]
        resumo[chave] = sum(valores) / len(valores) if valores else None
    return resumo


def _alvo_langsmith(alvo: Callable) -> Callable[[dict], dict]:
    return lambda inputs: _como_saida(alvo(inputs))


def enviar_ao_langsmith(
    alvo: Callable, nome_dataset: str = "incident-agent-cenarios", prefixo: str = "fase5"
) -> Any:
    """Cria (ou reusa) o dataset na conta do LangSmith e roda o experimento. Ação externa."""
    cliente = Client()
    if not cliente.has_dataset(dataset_name=nome_dataset):
        cliente.create_dataset(nome_dataset, description="Cenários de incidente do incident-agent")
        cliente.create_examples(dataset_name=nome_dataset, examples=exemplos_dataset())
    return evaluate(
        _alvo_langsmith(alvo),
        data=nome_dataset,
        evaluators=AVALIADORES,
        experiment_prefix=prefixo,
        max_concurrency=4,
    )
