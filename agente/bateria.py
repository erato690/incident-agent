"""Relatório da bateria de mensagens de teste: tabela-resumo por grupo e detalhe recolhível.

Reaproveitável nas próximas fases: cada mensagem do JSON traz `id`, `grupo`, `mensagem` e
`rota_esperada`; cada resultado é um `RespostaTurno`.
"""
from html import escape

from agente.mascara import mascarar
from agente.schemas import RespostaTurno

# Chave do JSON -> subtítulo exibido (a ordem define a ordem dos grupos no relatório).
GRUPOS = {
    "investigacao": "Investigação (cenários de erro)",
    "barreira": "Barreira (saudação, fora do escopo, pedido de ação, injeção, vazia)",
    "guardrails": "Guardrails (segredos mascarados, moderação com aviso)",
}


def _intencao(r: RespostaTurno) -> str:
    if r.nlu:
        return r.nlu.intencao
    return r.fixa.categoria if r.fixa else "-"


def _moderacao(r: RespostaTurno) -> str:
    m = r.moderacao
    return f"{m.status} ({', '.join(m.categorias)})" if m.categorias else m.status


def linhas_bateria(mensagens: list[dict], resultados: list[RespostaTurno]) -> list[dict]:
    """Uma linha por teste, com as colunas da tabela-resumo."""
    return [
        {"id": m["id"], "grupo": GRUPOS.get(m.get("grupo"), m.get("grupo", "-")),
         "esperada": m["rota_esperada"], "obtida": r.rota, "intenção": _intencao(r),
         "moderação": _moderacao(r), "ok": r.rota == m["rota_esperada"]}
        for m, r in zip(mensagens, resultados)
    ]


def detalhe_html(m: dict, r: RespostaTurno) -> str:
    """Bloco <details> com o que foi enviado e o que voltou (texto sempre escapado)."""
    ok = r.rota == m["rota_esperada"]
    mod = r.moderacao
    scores = ", ".join(f"{c}={s:.2f}" for c, s in mod.scores.items())
    itens = [
        f"<b>Mensagem enviada (mascarada):</b> <code>{escape(mascarar(m['mensagem'])) or '(vazia)'}</code>",
        f"<b>Moderação:</b> {escape(_moderacao(r))}" + (f" · scores: {escape(scores)}" if scores else ""),
        f"<b>Intenção do NLU:</b> {escape(_intencao(r))}",
    ]
    if r.analise:
        a = r.analise
        itens.append(f"<b>Severidade:</b> {a.severidade} · <b>Resumo:</b> {escape(a.resumo)}")
        hips = "".join(
            f"<li>{escape(h.causa)} — confiança {h.confianca:.2f} — evidência: "
            f"<code>{escape(h.evidencia)}</code>"
            + (" <i>(evidência insuficiente)</i>" if h.evidencia_insuficiente else "") + "</li>"
            for h in a.hipoteses)
        itens.append(f"<b>Hipóteses:</b><ol>{hips}</ol>")
    elif r.fixa:
        itens.append(f"<b>Resposta fixa (camada {r.fixa.camada}):</b> {escape(r.fixa.texto)}")
    elif r.erro:
        itens.append(f"<b>Erro:</b> {escape(r.erro)}")
    status = "ok" if ok else "FALHOU"
    cor = "#1a7f37" if ok else "#cf222e"
    corpo = "".join(f"<li>{i}</li>" for i in itens)
    return (f"<details><summary><b style='color:{cor}'>{escape(m['id'])} — {status}</b> "
            f"(esperada {m['rota_esperada']}, obtida {r.rota})</summary><ul>{corpo}</ul></details>")


def exibir_bateria(mensagens: list[dict], resultados: list[RespostaTurno], titulo: str = "Bateria") -> None:
    """Mostra no notebook: placar, tabela colorida e, por grupo, o detalhe de cada teste."""
    import pandas as pd
    from IPython.display import HTML, Markdown, display

    linhas = linhas_bateria(mensagens, resultados)
    acertos = sum(l["ok"] for l in linhas)
    display(Markdown(f"### {titulo}: {acertos}/{len(linhas)} rotas corretas"))
    tabela = pd.DataFrame(linhas)
    display(tabela.style.map(
        lambda v: f"background-color: {'#d1f7d6' if v else '#ffd7d5'}; font-weight: bold",
        subset=["ok"]).hide(axis="index"))
    pares = list(zip(mensagens, resultados))
    for chave in list(GRUPOS) + sorted({m.get("grupo") for m in mensagens} - set(GRUPOS)):
        do_grupo = [(m, r) for m, r in pares if m.get("grupo") == chave]
        if not do_grupo:
            continue
        ok = sum(r.rota == m["rota_esperada"] for m, r in do_grupo)
        display(Markdown(f"#### {GRUPOS.get(chave, chave)}: {ok}/{len(do_grupo)}"))
        display(HTML("".join(detalhe_html(m, r) for m, r in do_grupo)))
