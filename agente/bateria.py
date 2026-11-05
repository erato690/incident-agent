"""Relatório da bateria de mensagens de teste: tabela-resumo por grupo e detalhe recolhível.

Reaproveitável nas próximas fases: cada mensagem do JSON traz `id`, `grupo`, `mensagem` e
`rota_esperada` (e, na Fase 3, `registra_esperado`); cada resultado é um `RespostaTurno`.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from html import escape

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import Runnable

from agente.conversa import Conversa, abrir_sessao, texto_resposta
from agente.mascara import mascarar
from agente.schemas import AnaliseIncidente, RespostaTurno, Sessao

# Chave do JSON -> subtítulo exibido (a ordem define a ordem dos grupos no relatório).
GRUPOS = {
    "investigacao": "Investigação (cenários de erro)",
    "barreira": "Barreira (saudação, fora do escopo, pedido de ação, injeção, vazia, causa)",
    "guardrails": "Guardrails (segredos mascarados, moderação com aviso)",
    "memoria": "Memória (causa confirmada, perguntas, histórico, barreira)",
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


def memoria_registrada(resposta: RespostaTurno) -> str:
    """Episódio gravado neste turno: "registrado", "atualizado" (arquivou o anterior) ou "-"."""
    if resposta.episodio is None:
        return "fato registrado" if resposta.fato is not None else "-"
    return "atualizado" if resposta.episodio_anterior else "registrado"


def memoria_consultada(resposta: RespostaTurno) -> bool:
    """True quando a trajetória do turno chamou `consultar_memoria`."""
    return "consultar_memoria" in nomes_ferramentas(resposta)


def acertou(mensagem: dict, resposta: RespostaTurno) -> bool:
    """Rota esperada e, quando o item traz `registra_esperado` ou `grava_fato_esperado`, se
    gravou ou não um episódio ou um fato."""
    if resposta.rota != mensagem["rota_esperada"]:
        return False
    registra = mensagem.get("registra_esperado")
    if registra is not None and registra != (resposta.episodio is not None):
        return False
    grava_fato = mensagem.get("grava_fato_esperado")
    return grava_fato is None or grava_fato == (resposta.fato is not None)


def causa_certa(mensagem: dict, resposta: RespostaTurno) -> bool | None:
    """None sem `palavras_causa`; senão, True se a hipótese principal (maior confiança) cita
    alguma delas (sem diferenciar maiúsculas). Mede o diagnóstico, à parte da rota."""
    palavras = mensagem.get("palavras_causa")
    if not palavras:
        return None
    if resposta.analise is None or not resposta.analise.hipoteses:
        return False
    principal = max(resposta.analise.hipoteses, key=lambda h: h.confianca)
    texto = principal.causa.casefold()
    return any(palavra.casefold() in texto for palavra in palavras)


def _tem_registra(mensagem: dict) -> bool:
    return "registra_esperado" in mensagem or "grava_fato_esperado" in mensagem


def linhas_bateria(mensagens: list[dict], resultados: list[RespostaTurno]) -> list[dict]:
    """Uma linha por teste. As colunas "ferramentas" e "memória registrada"/"memória consultada"
    só aparecem se algum turno usou ferramentas ou mexeu na memória (Fases 1 e 2 não mudam)."""
    com_ferramentas = any(resposta.trajetoria for resposta in resultados)
    com_causa = any(mensagem.get("palavras_causa") for mensagem in mensagens)
    com_memoria = any(
        resposta.episodio
        or resposta.fato
        or memoria_consultada(resposta)
        or _tem_registra(mensagem)
        for mensagem, resposta in zip(mensagens, resultados, strict=True)
    )
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
        if com_memoria:
            linha["memória registrada"] = memoria_registrada(resposta)
            linha["memória consultada"] = "sim" if memoria_consultada(resposta) else "-"
        if com_causa:
            certa = causa_certa(mensagem, resposta)
            linha["causa certa"] = "-" if certa is None else ("sim" if certa else "não")
        linhas.append({**linha, "ok": acertou(mensagem, resposta)})
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


def _acoes_html(analise: AnaliseIncidente) -> str:
    itens = "".join(
        f"<li>{escape(acao.acao)} — risco {acao.risco} — {escape(acao.motivo)} "
        f"<i>({escape(acao.status)})</i></li>"
        for acao in analise.acoes_sugeridas
    )
    return f"<b>Ações sugeridas:</b><ul>{itens}</ul>"


def _itens_analise(mensagem: dict, analise: AnaliseIncidente) -> list[str]:
    itens = [
        f"<b>Severidade:</b> {analise.severidade} · <b>Resumo:</b> {escape(analise.resumo)}",
        _hipoteses_html(analise),
    ]
    if analise.acoes_sugeridas:
        itens.append(_acoes_html(analise))
    if mensagem.get("hipoteses_devem_considerar"):
        deve = "; ".join(mensagem["hipoteses_devem_considerar"])
        itens.append(f"<b>Deve considerar:</b> {escape(deve)}")
    return itens


def _episodio_html(resposta: RespostaTurno) -> str:
    episodio = resposta.episodio
    if resposta.rota == "memoria":
        rotulo = "Memória: episódio registrado"
        if resposta.episodio_anterior:
            rotulo = "Memória: episódio atualizado (anterior arquivado)"
    else:
        rotulo = f"Memória {memoria_registrada(resposta)}"
    texto = (
        f"<b>{rotulo}:</b> incidente "
        f"<code>{escape(episodio.incidente_id)}</code> · {escape(episodio.servico)} · "
        f"causa: {escape(episodio.causa)}"
    )
    if resposta.episodio_anterior:
        texto += f" · causa anterior (arquivada): {escape(resposta.episodio_anterior.causa)}"
    if resposta.resolucao:
        texto += (
            f" · decisão: {escape(resposta.resolucao.acao)} ({escape(resposta.resolucao.motivo)})"
        )
    return texto


def _itens_desfecho(mensagem: dict, resposta: RespostaTurno) -> list[str]:
    itens = []
    if resposta.analise:
        itens += _itens_analise(mensagem, resposta.analise)
    elif resposta.fixa:
        rotulo = (
            "Registro na memória episódica"
            if resposta.rota == "memoria"
            else f"Resposta fixa (camada {resposta.fixa.camada})"
        )
        itens.append(f"<b>{rotulo}:</b> {escape(resposta.fixa.texto)}")
    elif resposta.erro:
        itens.append(f"<b>Erro:</b> {escape(resposta.erro)}")
    if resposta.trajetoria:
        itens.append(_passos_html(resposta))
    if resposta.episodio:
        itens.append(_episodio_html(resposta))
    if mensagem.get("causa_esperada"):
        itens.append(
            f"<b>Causa esperada (informativo, não foi enviada ao modelo):</b> "
            f"{escape(mensagem['causa_esperada'])}"
        )
    return itens


def detalhe_html(mensagem: dict, resposta: RespostaTurno) -> str:
    """Bloco <details> com o que foi enviado e o que voltou (texto sempre escapado)."""
    certo = acertou(mensagem, resposta)
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
    status = "ok" if certo else "FALHOU"
    cor = "#1a7f37" if certo else "#cf222e"
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
        acertos_grupo = sum(acertou(msg, resp) for msg, resp in do_grupo)
        display(Markdown(f"#### {GRUPOS.get(chave, chave)}: {acertos_grupo}/{len(do_grupo)}"))
        display(HTML("".join(detalhe_html(msg, resp) for msg, resp in do_grupo)))


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
            {
                "mensagem": mensagem["mensagem"],
                "historico": [],
                "incidente_id": mensagem["id"],
                "session_id": f"bateria-{mensagem['id']}",
            }
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


ConversaOuFabrica = Conversa | Callable[[str], Conversa]


def rodar_conversa_sessao(
    origem: ConversaOuFabrica, conversa: dict, sessao: Sessao | None = None
) -> list[RespostaTurno]:
    """Roda os turnos numa sessão nova (a memória de curto prazo guarda o histórico).

    `origem` é uma `Conversa` ou uma fábrica `cenario -> Conversa`; o cenário vem da conversa e
    nunca é enviado ao modelo. Passe `sessao` para inspecionar turnos e serviço depois."""
    if isinstance(origem, Conversa):
        grafo = origem
    else:
        if conversa.get("cenario") is None:
            raise ValueError("fábrica de conversa exige `cenario` na conversa")
        grafo = origem(conversa["cenario"])
    sessao = sessao or abrir_sessao(cenario=conversa.get("cenario"))
    return [grafo.turno(sessao, turno["mensagem"]) for turno in conversa["turnos"]]


def _profundidade(conversas: list[dict], i: int) -> int:
    """Quantas dependências encadeadas a conversa `i` tem dentro da lista (0 = independente)."""
    indice = {conversa["id"]: j for j, conversa in enumerate(conversas)}
    passos = 0
    while (pai := indice.get(conversas[i].get("depende_de"))) is not None and passos < len(
        conversas
    ):
        i, passos = pai, passos + 1
    return passos


def _linhas_de_execucao(conversas: list[dict]) -> list[list[int]]:
    """Índices agrupados por linha: quem depende de outra conversa da lista vai na linha dela."""
    indice = {conversa["id"]: i for i, conversa in enumerate(conversas)}

    def raiz(i: int) -> int:
        visitados = {i}
        while (pai := indice.get(conversas[i].get("depende_de"))) is not None:
            if pai in visitados:
                break
            visitados.add(pai)
            i = pai
        return i

    linhas: dict[int, list[int]] = {}
    for i in range(len(conversas)):
        linhas.setdefault(raiz(i), []).append(i)
    return list(linhas.values())


def rodar_conversas_paralelas(
    origem: ConversaOuFabrica, conversas: list[dict], max_workers: int = 4
) -> list[list[RespostaTurno]]:
    """Roda conversas independentes em paralelo; `depende_de` mantém a ordem na mesma linha.

    Cada linha de execução roda suas conversas em sequência (a dependência primeiro, na ordem da
    lista); o resultado volta na ordem original de `conversas`."""
    resultados: list[list[RespostaTurno]] = [[] for _ in conversas]

    def rodar_linha(linha: list[int]) -> None:
        for i in sorted(linha, key=lambda j: _profundidade(conversas, j)):
            resultados[i] = rodar_conversa_sessao(origem, conversas[i])

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for futuro in [
            executor.submit(rodar_linha, linha) for linha in _linhas_de_execucao(conversas)
        ]:
            futuro.result()
    return resultados
