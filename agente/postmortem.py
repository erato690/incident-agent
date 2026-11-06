"""Post-mortem em markdown: único atuador do agente, gerado por template em código."""

import re
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from agente.mascara import mascarar
from agente.qualidade import _normalizar
from agente.schemas import AnaliseIncidente, Auditoria, Episodio, PassoTrajetoria

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
    auditoria: Auditoria | None = None
    auditada_em: datetime | None = None


_DATA_HORA = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}):\d{2}")
_DEPLOY = re.compile(
    r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}):\d{2}\S* (\S+/v[\d.]+) \(previous: (\S+)\)[^:]*: (.*)"
)
_LOG = re.compile(r"^\[(\w+)\] (.*?) \(x(\d+), (\d{2}:\d{2}):\d{2} a (\d{2}:\d{2}):\d{2}\)")
_RETRATO = re.compile(r"retrato de (\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})")
_REINDEX = re.compile(
    r"^(\w+):.*(reindexação em andamento: sim|operação em andamento: (?!nenhuma)[^,]+)"
)


def _data_do_incidente(trajetoria: list[PassoTrajetoria]) -> str | None:
    """Data dos eventos (deploys e retratos têm data; os logs só trazem a hora)."""
    for passo in trajetoria:
        achado = _DATA_HORA.search(passo.observacao or "")
        if achado:
            return achado.group(1)
    return None


def linha_do_tempo_do_incidente(trajetoria: list[PassoTrajetoria]) -> list[ItemLinhaDoTempo]:
    """Só eventos do incidente, em ordem cronológica e com data: deploys, primeiro e último erro
    dos logs e operação em andamento no banco. Consultas, retratos e avisos técnicos ficam de fora
    (a investigação vai para a seção própria)."""
    data = _data_do_incidente(trajetoria)
    itens: list[ItemLinhaDoTempo] = []
    for passo in trajetoria:
        observacao = passo.observacao or ""
        if passo.ferramenta == "listar_deploys":
            for dia, hora, tag, anterior, mensagem in _DEPLOY.findall(observacao):
                evento = f"Deploy {tag} (anterior {anterior}): {mensagem.strip()[:160]}"
                itens.append(
                    ItemLinhaDoTempo(horario=f"{dia} {hora}", evento=evento, fonte="deploys")
                )
        elif passo.ferramenta == "buscar_logs":
            for linha in observacao.splitlines():
                achado = _LOG.match(linha.strip())
                if not achado:
                    continue
                _, mensagem, vezes, inicio, fim = achado.groups()
                prefixo = f"{data} " if data else ""
                resumo = mensagem.split(" | ")[0][:140]
                itens.append(
                    ItemLinhaDoTempo(
                        horario=f"{prefixo}{inicio}",
                        evento=f"Primeiro erro registrado ({vezes} ocorrências até {fim}): "
                        f"{resumo}",
                        fonte="logs",
                    )
                )
                itens.append(
                    ItemLinhaDoTempo(
                        horario=f"{prefixo}{fim}",
                        evento=f"Último erro registrado: {resumo[:80]}",
                        fonte="logs",
                    )
                )
        elif passo.ferramenta == "consultar_estatisticas_banco":
            retrato = _RETRATO.search(observacao)
            for linha in observacao.splitlines():
                achado = _REINDEX.match(linha.strip())
                if achado and retrato:
                    tabela = achado.group(1)
                    itens.append(
                        ItemLinhaDoTempo(
                            horario=f"{retrato.group(1)} {retrato.group(2)}",
                            evento=f"Banco com reindexação em andamento na tabela {tabela}",
                            fonte="estatísticas do banco",
                        )
                    )
    unicos = {(i.horario, i.evento): i for i in itens}
    return sorted(unicos.values(), key=lambda item: item.horario or "")


def _nota_reserva(passo: PassoTrajetoria) -> str:
    motivo = passo.motivo_reserva or ""
    if "GitHub limit of 60" in motivo:
        return (
            "usou dados gravados (limite de 60 requisições por hora da API do GitHub sem token "
            "esgotado)"
        )
    if re.search(r"[Ff]allback|network|timeout|limit", motivo):
        return "usou dados gravados (a fonte ao vivo não respondeu)"
    return f"nota: {motivo}" if motivo else "usou dados gravados"


def investigacao_realizada(trajetoria: list[PassoTrajetoria]) -> list[str]:
    """Consultas feitas pelo agente, em ordem, com nota em português quando usou dados gravados."""
    linhas = []
    for passo in trajetoria:
        argumentos = ", ".join(f"{k}={str(v)[:60]}" for k, v in passo.argumentos.items())
        linha = f"- {passo.ferramenta}({argumentos})"
        if passo.reserva:
            linha += f" - {_nota_reserva(passo)}"
        if passo.erro:
            linha += " - a consulta falhou"
        linhas.append(linha)
    return linhas


def _titulo(dados: DadosPostMortem) -> str:
    return f"# Post-mortem {dados.incidente_id} - {dados.servico}"


def _secao_impacto(dados: DadosPostMortem) -> list[str]:
    analise = dados.analise
    if not analise:
        return ["Severidade e categoria não avaliadas."]
    return [f"- Severidade: {analise.severidade}", f"- Categoria: {analise.categoria}"]


def _secao_linha_do_tempo(dados: DadosPostMortem) -> list[str]:
    itens = dados.linha_do_tempo or linha_do_tempo_do_incidente(dados.trajetoria)
    if not itens:
        return ["Sem eventos com horário nas observações."]
    return [f"- {i.horario} - {i.evento} (fonte: {i.fonte})" for i in itens]


def _secao_causa(dados: DadosPostMortem) -> list[str]:
    linhas = [f"Causa confirmada: {dados.episodio.causa}"]
    if dados.episodio.evidencia:
        linhas.append(f"Evidência: {dados.episodio.evidencia}")
    elif dados.analise and dados.analise.hipoteses[0].evidencia:
        linhas.append(f"Evidência: {dados.analise.hipoteses[0].evidencia}")
    return linhas


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


_VAZIAS = {"a", "o", "as", "os", "de", "do", "da", "dos", "das", "e", "em", "no", "na", "para"}
_VERBOS_CORRECAO = {"aumentar", "restaurar", "reverter", "ajustar", "voltar", "rollback", "fazer"}


def _termos(texto: str) -> set[str]:
    """Termos com `pool_max` partido em `pool` e `max`; sem palavras vazias nem verbos."""
    palavras = re.findall(r"[a-z0-9.]+", _normalizar(texto).replace("_", " "))
    return {p for p in palavras if p not in _VAZIAS | _VERBOS_CORRECAO}


def _comum(a: str, b: str) -> bool:
    """Mesmo termo, ou prefixo de 3+ letras (max e maximo)."""
    return a == b or (min(len(a), len(b)) >= 3 and (a.startswith(b) or b.startswith(a)))


def _repete_correcao(passo: str, acoes: list) -> bool:
    """O passo diz o mesmo que uma ação de correção (ex.: "aumentar o pool máximo para 20" e
    "Restaurar pool_max para 20"), ou é ele mesmo uma correção (rollback, restaurar)."""
    termos = _termos(passo)
    for acao in acoes:
        outros = _termos(acao.acao)
        comuns = [t for t in outros if any(_comum(t, u) for u in termos)]
        if outros and len(comuns) / len(outros) >= 0.6:
            return True
    return bool(re.match(r"(rollback|reverter|restaurar|desfazer|voltar)", _normalizar(passo)))


def _secao_preventivas(dados: DadosPostMortem) -> list[str]:
    """Só o que evita recorrência: o passo que repete a correção sugerida sai."""
    passos = dados.analise.proximos_passos if dados.analise else []
    acoes = dados.analise.acoes_sugeridas if dados.analise else []
    distintos = [p for p in passos if not _repete_correcao(p, acoes)]
    return [f"- {p}" for p in distintos] or ["Nenhuma ação preventiva distinta da correção."]


def _secao_licoes(dados: DadosPostMortem) -> list[str]:
    return [f"- {dados.episodio.resumo}"]


def _secao_investigacao(dados: DadosPostMortem) -> list[str]:
    return investigacao_realizada(dados.trajetoria) or ["Nenhuma consulta registrada."]


def _rodape(dados: DadosPostMortem) -> str:
    auditoria = dados.auditoria
    if auditoria is None:
        return "Auditoria: não auditada."
    situacao = "aprovada" if auditoria.aprovada else "reprovada"
    veredito = f", veredito {auditoria.veredito}" if auditoria.veredito else ""
    quando = f" (auditada em {dados.auditada_em:%Y-%m-%d %H:%M})" if dados.auditada_em else ""
    return f"Auditoria: {situacao}{veredito}{quando}."


def gerar_postmortem(dados: DadosPostMortem) -> str:
    """Monta o markdown do template da constituição, com segredos mascarados. Só com a causa
    confirmada pelo engenheiro (episódio registrado): sem ela, não há post-mortem."""
    if dados.episodio is None:
        raise ValueError("post-mortem só com causa confirmada pelo engenheiro")
    resumo = dados.analise.resumo if dados.analise else _SEM_DADO
    secoes = [
        ("Resumo", [resumo, f"Gerado em: {dados.gerado_em:%Y-%m-%d %H:%M}"]),
        ("Impacto e severidade", _secao_impacto(dados)),
        ("Linha do tempo", _secao_linha_do_tempo(dados)),
        ("Causa raiz e evidências", _secao_causa(dados)),
        ("Correção sugerida (comando para o humano rodar)", _secao_acoes(dados)),
        ("Ações preventivas", _secao_preventivas(dados)),
        ("Lições aprendidas", _secao_licoes(dados)),
        ("Investigação realizada", _secao_investigacao(dados)),
    ]
    blocos = [_titulo(dados)]
    for nome, linhas in secoes:
        blocos.append(f"## {nome}\n\n" + "\n".join(linhas))
    blocos.append(f"---\n\n{_rodape(dados)}")
    return mascarar("\n\n".join(blocos) + "\n")


def salvar_postmortem(dados: DadosPostMortem, pasta: Path | str) -> Path:
    destino = Path(pasta)
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"postmortem_{dados.incidente_id}.md"
    caminho.write_text(gerar_postmortem(dados), encoding="utf-8")
    return caminho
