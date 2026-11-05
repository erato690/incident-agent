"""Post-mortem em markdown: único atuador do agente, gerado por template em código."""

import re
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from agente.mascara import mascarar
from agente.schemas import AnaliseIncidente, Episodio, PassoTrajetoria

_HORARIO = re.compile(r"\b([01]\d|2[0-3]):[0-5]\d\b")
_SEM_DADO = "Não informado."


class ItemLinhaDoTempo(BaseModel):
    horario: str | None = None
    evento: str
    fonte: str


class DadosPostMortem(BaseModel):
    incidente_id: str
    servico: str
    gerado_em: datetime
    analise: AnaliseIncidente | None = None
    episodio: Episodio | None = None
    linha_do_tempo: list[ItemLinhaDoTempo] = Field(default_factory=list)
    trajetoria: list[PassoTrajetoria] = Field(default_factory=list)


def _horarios(texto: str) -> list[str]:
    return [m.group() for m in _HORARIO.finditer(texto)]


def linha_do_tempo_da_trajetoria(trajetoria: list[PassoTrajetoria]) -> list[ItemLinhaDoTempo]:
    """Um item por ferramenta chamada, mais os horários HH:MM citados nas observações."""
    itens: list[ItemLinhaDoTempo] = []
    for passo in trajetoria:
        argumentos = ", ".join(f"{k}={v}" for k, v in passo.argumentos.items())
        itens.append(
            ItemLinhaDoTempo(
                horario=None,
                evento=f"Consulta {passo.ferramenta}({argumentos})",
                fonte="trajetoria",
            )
        )
        observacao = getattr(passo, "observacao", None) or ""
        for horario in dict.fromkeys(_horarios(observacao)):
            trecho = next(
                (linha.strip() for linha in observacao.splitlines() if horario in linha), ""
            )
            itens.append(
                ItemLinhaDoTempo(horario=horario, evento=trecho[:200], fonte=passo.ferramenta)
            )
    return sorted(itens, key=lambda item: item.horario or "99:99")


def _titulo(dados: DadosPostMortem) -> str:
    sufixo = "" if dados.episodio else " (causa não confirmada)"
    return f"# Post-mortem {dados.incidente_id} - {dados.servico}{sufixo}"


def _secao_impacto(dados: DadosPostMortem) -> list[str]:
    analise = dados.analise
    if not analise:
        return ["Severidade e categoria não avaliadas."]
    return [f"- Severidade: {analise.severidade}", f"- Categoria: {analise.categoria}"]


def _secao_linha_do_tempo(dados: DadosPostMortem) -> list[str]:
    itens = dados.linha_do_tempo or linha_do_tempo_da_trajetoria(dados.trajetoria)
    if not itens:
        return [_SEM_DADO]
    return [f"- {i.horario or 'sem horário'} - {i.evento} (fonte: {i.fonte})" for i in itens]


def _secao_causa(dados: DadosPostMortem) -> list[str]:
    if dados.episodio:
        linhas = [f"Causa confirmada: {dados.episodio.causa}"]
        if dados.episodio.evidencia:
            linhas.append(f"Evidência: {dados.episodio.evidencia}")
        return linhas
    hipoteses = dados.analise.hipoteses if dados.analise else []
    texto = "; ".join(f"{h.causa} (confiança {h.confianca:.0%})" for h in hipoteses)
    return [f"Causa não confirmada pelo engenheiro; hipóteses: {texto or 'nenhuma'}."]


def _secao_acoes(dados: DadosPostMortem) -> list[str]:
    acoes = dados.analise.acoes_sugeridas if dados.analise else []
    if not acoes:
        return ["Nenhuma ação sugerida."]
    return [
        f"- {a.acao} - {a.motivo} (risco {a.risco}"
        + (f"; runbook: {a.runbook}" if a.runbook else "")
        + f") - {a.status}"
        for a in acoes
    ]


def _secao_preventivas(dados: DadosPostMortem) -> list[str]:
    passos = dados.analise.proximos_passos if dados.analise else []
    return [f"- {p}" for p in passos] or [_SEM_DADO]


def _secao_licoes(dados: DadosPostMortem) -> list[str]:
    if dados.episodio:
        return [f"- {dados.episodio.resumo}"]
    return ["Sem lições registradas: a causa ainda não foi confirmada."]


def gerar_postmortem(dados: DadosPostMortem) -> str:
    """Monta o markdown do template da constituição, com segredos mascarados."""
    resumo = dados.analise.resumo if dados.analise else _SEM_DADO
    secoes = [
        ("Resumo", [resumo, f"Gerado em: {dados.gerado_em:%Y-%m-%d %H:%M}"]),
        ("Impacto e severidade", _secao_impacto(dados)),
        ("Linha do tempo", _secao_linha_do_tempo(dados)),
        ("Causa raiz e evidências", _secao_causa(dados)),
        ("Correção sugerida (comando para o humano rodar)", _secao_acoes(dados)),
        ("Ações preventivas", _secao_preventivas(dados)),
        ("Lições aprendidas", _secao_licoes(dados)),
    ]
    blocos = [_titulo(dados)]
    for nome, linhas in secoes:
        blocos.append(f"## {nome}\n\n" + "\n".join(linhas))
    return mascarar("\n\n".join(blocos) + "\n")


def salvar_postmortem(dados: DadosPostMortem, pasta: Path | str) -> Path:
    destino = Path(pasta)
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"postmortem_{dados.incidente_id}.md"
    caminho.write_text(gerar_postmortem(dados), encoding="utf-8")
    return caminho
