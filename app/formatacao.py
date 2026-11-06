"""Formatação pura das respostas e do registro (sem Streamlit, testável sem chave)."""

import json
from pathlib import Path

from agente.registro import RegistroTurno
from agente.schemas import RespostaTurno

AVISO_RODAPE = "O agente só lê e sugere; nunca executa ações em produção."


def selo_auditoria(resposta: RespostaTurno) -> str:
    auditoria = resposta.auditoria
    if auditoria is None:
        return "auditada: não auditada"
    return "auditada: aprovada" if auditoria.aprovada else "auditada: reprovada"


def _bloco_analise(resposta: RespostaTurno) -> list[str]:
    analise = resposta.analise
    linhas = [f"**Severidade:** {analise.severidade} · **Categoria:** {analise.categoria}"]
    linhas += ["", analise.resumo, "", "**Hipóteses**"]
    for h in analise.hipoteses:
        evidencia = h.evidencia or "sem evidência direta"
        linha = f"- {h.causa} (confiança {h.confianca:.0%}). Evidência: {evidencia}"
        if h.dado_que_falta:
            linha += f" Falta: {h.dado_que_falta}"
        linhas.append(linha)
    if analise.acoes_sugeridas:
        linhas += ["", "**Ações sugeridas**"]
        for a in analise.acoes_sugeridas:
            origem = f", runbook: {a.runbook}" if a.runbook else ""
            linhas.append(
                f"- {a.acao} (sugerida, não executada). {a.motivo} Risco: {a.risco}{origem}"
            )
    return linhas


def markdown_resposta(resposta: RespostaTurno) -> str:
    linhas: list[str] = []
    if resposta.aviso:
        linhas += [f"> **ATENÇÃO:** {resposta.aviso}", ""]
    if resposta.analise is not None:
        linhas += _bloco_analise(resposta)
    elif resposta.fixa is not None:
        linhas.append(resposta.fixa.texto)
    else:
        linhas.append(f"**Erro:** {resposta.erro or 'sem detalhes'}")
    linhas += ["", f"*{selo_auditoria(resposta)}*"]
    return "\n".join(linhas)


def linhas_registro(registros: list[RegistroTurno]) -> list[dict]:
    return [
        {
            "hora": r.criado_em.strftime("%H:%M:%S"),
            "sessão": r.session_id[:8],
            "pergunta": r.pergunta,
            "rota": r.rota,
            "ferramentas": ", ".join(r.ferramentas),
            "auditoria": _rotulo_auditoria(r.auditoria_aprovada),
            "duração (ms)": r.duracao_ms,
        }
        for r in registros
    ]


def _rotulo_auditoria(aprovada: bool | None) -> str:
    if aprovada is None:
        return "não auditada"
    return "aprovada" if aprovada else "reprovada"


def cenarios_disponiveis(pasta: Path | str) -> list[dict]:
    """Lê o bloco `cenario` de cada JSON da pasta, ordenado por título."""
    itens = []
    for arquivo in sorted(Path(pasta).glob("*.json")):
        dados = json.loads(arquivo.read_text(encoding="utf-8")).get("cenario")
        if dados and "id" in dados:
            itens.append(
                {
                    "id": dados["id"],
                    "titulo": dados.get("titulo", dados["id"]),
                    "servico": dados.get("servico"),
                }
            )
    return sorted(itens, key=lambda c: c["titulo"])


# --- Apoio à API do chat (funções puras) ---

ROTULO_FERRAMENTA = {
    "buscar_logs": "logs da loja",
    "buscar_metricas": "métricas",
    "listar_deploys": "deploys",
    "comparar_versoes": "diff entre versões",
    "consultar_estatisticas_banco": "estatísticas do banco",
    "consultar_memoria": "incidentes anteriores",
    "gravar_episodio": "registro da causa",
    "buscar_documentacao": "documentação indexada",
    "consultar_wiki": "wiki de fatos",
    "gravar_fato": "registro de fato",
    "sugerir_acao": "runbooks (ações sugeridas)",
    "consultar_sql": "histórico de incidentes (SQL)",
}


def rotulo_ferramenta(nome: str) -> str:
    return ROTULO_FERRAMENTA.get(nome, nome)


def dados_faltantes(resposta: RespostaTurno) -> list[str]:
    """Perguntas ao engenheiro: o dado faltante do NLU e o da hipótese principal, quando ela não
    tem evidência. O dado que falta das hipóteses secundárias fica junto delas."""
    itens: list[str] = []
    if resposta.analise is not None:
        principal = resposta.analise.hipoteses[0]
        if principal.evidencia_insuficiente and principal.dado_que_falta:
            itens.append(principal.dado_que_falta)
    if resposta.nlu is not None and getattr(resposta.nlu, "dado_faltante", None):
        itens.append(resposta.nlu.dado_faltante)
    unicos: dict[str, str] = {}
    for item in itens:
        unicos.setdefault(item.casefold(), item)
    return list(unicos.values())


def fontes_consultadas(resposta: RespostaTurno) -> list[str]:
    """Rótulos das ferramentas chamadas, na ordem da primeira chamada."""
    nomes = dict.fromkeys(p.ferramenta for p in resposta.trajetoria)
    return [rotulo_ferramenta(n) for n in nomes]


def mensagem_erro(excecao: BaseException) -> str:
    """Texto legível para falha inesperada do turno (sem pilha de chamadas)."""
    nome = type(excecao).__name__
    detalhe = str(excecao).strip().splitlines()[0][:200] if str(excecao).strip() else ""
    base = "Não consegui concluir a investigação deste turno"
    return f"{base} ({nome}{': ' + detalhe if detalhe else ''}). Tente de novo ou reformule."
