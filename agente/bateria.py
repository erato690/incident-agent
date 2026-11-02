"""Relatório da bateria de mensagens de teste: tabela-resumo por grupo e detalhe recolhível.

Reaproveitável nas próximas fases: cada mensagem do JSON traz `id`, `grupo`, `mensagem` e
`rota_esperada`; cada resultado é um `RespostaTurno`.
"""

from collections.abc import Callable
from html import escape

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import Runnable

from agente.mascara import mascarar
from agente.schemas import AnaliseIncidente, RespostaTurno

# Chave do JSON -> subtítulo exibido (a ordem define a ordem dos grupos no relatório).
GRUPOS = {
    "investigacao": "Investigação (cenários de erro)",
    "barreira": "Barreira (saudação, fora do escopo, pedido de ação, injeção, vazia, causa)",
    "guardrails": "Guardrails (segredos mascarados, moderação com aviso)",
}


def _intencao(resposta: RespostaTurno) -> str:
    if resposta.nlu:
        return resposta.nlu.intencao
    return resposta.fixa.categoria if resposta.fixa else "-"


def _moderacao(resposta: RespostaTurno) -> str:
    moderacao = resposta.moderacao
    categorias = ", ".join(moderacao.categorias)
    return f"{moderacao.status} ({categorias})" if categorias else moderacao.status


def nomes_ferramentas(resposta: RespostaTurno) -> list[str]:
    """Ferramentas da trajetória, na ordem, sem repetição consecutiva."""
    nomes: list[str] = []
    for passo in resposta.trajetoria:
        if not nomes or nomes[-1] != passo.ferramenta:
            nomes.append(passo.ferramenta)
    return nomes


def linhas_bateria(mensagens: list[dict], resultados: list[RespostaTurno]) -> list[dict]:
    """Uma linha por teste; a coluna "ferramentas" só aparece se algum turno usou ferramentas."""
    com_ferramentas = any(resposta.trajetoria for resposta in resultados)
    linhas = []
    for mensagem, resposta in zip(mensagens, resultados, strict=True):
        linha = {
            "id": mensagem["id"],
            "grupo": GRUPOS.get(mensagem.get("grupo"), mensagem.get("grupo", "-")),
            "esperada": mensagem["rota_esperada"],
            "obtida": resposta.rota,
            "intenção": _intencao(resposta),
            "moderação": _moderacao(resposta),
        }
        if com_ferramentas:
            linha["ferramentas"] = " → ".join(nomes_ferramentas(resposta)) or "-"
        linhas.append({**linha, "ok": resposta.rota == mensagem["rota_esperada"]})
    return linhas


def _passos_html(resposta: RespostaTurno) -> str:
    itens = "".join(
        f"<li><code>{escape(passo.ferramenta)}</code>"
        f"({escape(mascarar(str(passo.argumentos)))}) · {passo.duracao_ms} ms"
        + (" · <b>reserva gravada</b>" if passo.reserva else "")
        + (f" · erro: {escape(passo.erro)}" if passo.erro else "")
        + "</li>"
        for passo in resposta.trajetoria
    )
    return f"<b>Ferramentas chamadas:</b><ol>{itens}</ol>"


def _hipoteses_html(analise: AnaliseIncidente) -> str:
    itens = ""
    for hipotese in analise.hipoteses:
        evidencia = (
            f"evidência: <code>{escape(hipotese.evidencia)}</code>"
            if hipotese.evidencia
            else "sem evidência no texto"
        )
        insuficiente = (
            f" <i>(evidência insuficiente; falta: {escape(hipotese.dado_que_falta or '-')})</i>"
            if hipotese.evidencia_insuficiente
            else ""
        )
        itens += (
            f"<li>{escape(hipotese.causa)} — confiança {hipotese.confianca:.2f} — "
            f"{evidencia}{insuficiente}</li>"
        )
    return f"<b>Hipóteses:</b><ol>{itens}</ol>"


def _itens_analise(mensagem: dict, analise: AnaliseIncidente) -> list[str]:
    itens = [
        f"<b>Severidade:</b> {analise.severidade} · <b>Resumo:</b> {escape(analise.resumo)}",
        _hipoteses_html(analise),
    ]
    if mensagem.get("hipoteses_devem_considerar"):
        deve = "; ".join(mensagem["hipoteses_devem_considerar"])
        itens.append(f"<b>Deve considerar:</b> {escape(deve)}")
    return itens


def _itens_desfecho(mensagem: dict, resposta: RespostaTurno) -> list[str]:
    itens = []
    if resposta.analise:
        itens += _itens_analise(mensagem, resposta.analise)
    elif resposta.fixa:
        itens.append(
            f"<b>Resposta fixa (camada {resposta.fixa.camada}):</b> {escape(resposta.fixa.texto)}"
        )
    elif resposta.erro:
        itens.append(f"<b>Erro:</b> {escape(resposta.erro)}")
    if resposta.trajetoria:
        itens.append(_passos_html(resposta))
    if mensagem.get("causa_esperada"):
        itens.append(
            f"<b>Causa esperada (informativo, não foi enviada ao modelo):</b> "
            f"{escape(mensagem['causa_esperada'])}"
        )
    return itens


def detalhe_html(mensagem: dict, resposta: RespostaTurno) -> str:
    """Bloco <details> com o que foi enviado e o que voltou (texto sempre escapado)."""
    acertou = resposta.rota == mensagem["rota_esperada"]
    scores = ", ".join(
        f"{categoria}={score:.2f}" for categoria, score in resposta.moderacao.scores.items()
    )
    enviada = escape(mascarar(mensagem["mensagem"])) or "(vazia)"
    itens = [
        f"<b>Mensagem enviada (mascarada):</b> <code>{enviada}</code>",
        f"<b>Moderação:</b> {escape(_moderacao(resposta))}"
        + (f" · scores: {escape(scores)}" if scores else ""),
        f"<b>Intenção (etapa de compreensão):</b> {escape(_intencao(resposta))}",
        *_itens_desfecho(mensagem, resposta),
    ]
    status = "ok" if acertou else "FALHOU"
    cor = "#1a7f37" if acertou else "#cf222e"
    corpo = "".join(f"<li>{item}</li>" for item in itens)
    return (
        f"<details><summary><b style='color:{cor}'>{escape(mensagem['id'])} — {status}</b> "
        f"(esperada {mensagem['rota_esperada']}, obtida {resposta.rota})</summary>"
        f"<ul>{corpo}</ul></details>"
    )


def _colorir_ok(valor: bool) -> str:
    return f"background-color: {'#d1f7d6' if valor else '#ffd7d5'}; font-weight: bold"


def exibir_bateria(
    mensagens: list[dict], resultados: list[RespostaTurno], titulo: str = "Bateria"
) -> None:
    """Mostra no notebook: placar, tabela colorida e, por grupo, o detalhe de cada teste."""
    import pandas as pd
    from IPython.display import HTML, Markdown, display

    linhas = linhas_bateria(mensagens, resultados)
    acertos = sum(linha["ok"] for linha in linhas)
    display(Markdown(f"### {titulo}: {acertos}/{len(linhas)} rotas corretas"))
    tabela = pd.DataFrame(linhas)
    display(tabela.style.map(_colorir_ok, subset=["ok"]).hide(axis="index"))
    pares = list(zip(mensagens, resultados, strict=True))
    for chave in list(GRUPOS) + sorted({msg.get("grupo") for msg in mensagens} - set(GRUPOS)):
        do_grupo = [(msg, resp) for msg, resp in pares if msg.get("grupo") == chave]
        if not do_grupo:
            continue
        acertos_grupo = sum(resp.rota == msg["rota_esperada"] for msg, resp in do_grupo)
        display(Markdown(f"#### {GRUPOS.get(chave, chave)}: {acertos_grupo}/{len(do_grupo)}"))
        display(HTML("".join(detalhe_html(msg, resp) for msg, resp in do_grupo)))


def texto_resposta(resposta: RespostaTurno) -> str:
    """Texto curto da resposta do agente, para entrar no histórico da conversa."""
    if resposta.fixa:
        return resposta.fixa.texto
    if resposta.analise:
        hipoteses = [f"- {hip.causa} ({hip.confianca:.2f})" for hip in resposta.analise.hipoteses]
        return "\n".join([resposta.analise.resumo, *hipoteses])
    return resposta.erro or ""


PipelineOuFabrica = Runnable | Callable[[str], Runnable]


def _pipeline(origem: PipelineOuFabrica, cenario: str | None, cache: dict) -> Runnable:
    """Pipeline fixo, ou o da fábrica para o cenário (um por cenário, reaproveitado)."""
    if isinstance(origem, Runnable):
        return origem
    if cenario is None:
        raise ValueError("fábrica de pipeline exige `cenario` na mensagem ou na conversa")
    if cenario not in cache:
        cache[cenario] = origem(cenario)
    return cache[cenario]


def rodar_bateria(origem: PipelineOuFabrica, mensagens: list[dict]) -> list[RespostaTurno]:
    """Roda cada mensagem (sem histórico). `origem` é um pipeline fixo ou uma fábrica
    `cenario -> pipeline`; o cenário vem do JSON e nunca é enviado ao modelo."""
    cache: dict = {}
    return [
        _pipeline(origem, mensagem.get("cenario"), cache).invoke(
            {"mensagem": mensagem["mensagem"], "historico": []}
        )
        for mensagem in mensagens
    ]


def rodar_conversa(origem: PipelineOuFabrica, conversa: dict) -> list[RespostaTurno]:
    """Roda os turnos em ordem, acumulando o histórico (pergunta e resposta de cada turno).
    O cenário vem de `conversa["cenario"]` (ou do turno), quando `origem` é uma fábrica."""
    historico: list[BaseMessage] = []
    resultados, cache = [], {}
    for turno in conversa["turnos"]:
        pipeline = _pipeline(origem, turno.get("cenario", conversa.get("cenario")), cache)
        resposta = pipeline.invoke({"mensagem": turno["mensagem"], "historico": list(historico)})
        historico += [HumanMessage(turno["mensagem"]), AIMessage(texto_resposta(resposta))]
        resultados.append(resposta)
    return resultados


def exibir_conversa(conversa: dict, resultados: list[RespostaTurno]) -> None:
    """Mostra uma conversa com a mesma tabela e detalhe da bateria, um item por turno."""
    mensagens = [
        {**turno, "id": f"{conversa['id']} · turno {indice}", "grupo": conversa["titulo"]}
        for indice, turno in enumerate(conversa["turnos"], 1)
    ]
    exibir_bateria(mensagens, resultados, titulo=conversa["titulo"])
