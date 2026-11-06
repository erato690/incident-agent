"""Travas determinísticas de qualidade da resposta (depois do modelo, antes do auditor).

- Dado faltante só vale para o que SÓ o engenheiro sabe: nunca a causa, a própria pergunta ou
  algo que as ferramentas (logs, métricas, deploys, diff, wiki, documentação, histórico) alcançam.
- Ação sugerida é remediação: "verificar os logs" ou "consultar o limite documentado" não é ação.
- Próximo passo não devolve ao engenheiro uma consulta que o agente já fez.
"""

import re
import unicodedata

from agente.schemas import AnaliseIncidente, AnaliseNLU


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.casefold().split())


# Objeto da consulta -> ferramentas que já trazem esse dado.
OBJETOS = {
    r"\blogs?\b|\berros? nos logs\b": {"buscar_logs"},
    r"\bmetricas?\b|\bvolume de requisic|\btaxa de requisic|\bcpu\b|\blatencia\b": {
        "buscar_metricas"
    },
    r"\bdeploys?\b|\bimplantac": {"listar_deploys"},
    r"\bdiff\b|\bversoes\b|\bmudancas? (da|na|entre) vers": {"comparar_versoes"},
    r"\bwiki\b|\blimite documentado\b|\bdocumentac|\brunbooks?\b": {
        "consultar_wiki",
        "buscar_documentacao",
        "sugerir_acao",
    },
    r"\bestatisticas? do banco\b|\bvarreduras?\b|\breindexac": {"consultar_estatisticas_banco"},
    r"\bhistorico de incidentes\b|\bincidentes anteriores\b": {
        "consultar_memoria",
        "consultar_sql",
    },
}
VERBOS_CONSULTA = (
    r"^(verifi|consult|chec|cheq|confer|confir|analis|investig|revis|examin|olh|busc|identific|"
    r"levant|avali|observ|acompanh|inspecion)\w*"
)
CAUSA = r"\b(causa|causas|motivo|razao|origem|raiz|por que|porque|diagnostico)\b"
PALAVRAS_VAZIAS = {
    "a", "o", "as", "os", "de", "do", "da", "dos", "das", "e", "em", "no", "na", "nos", "nas",
    "um", "uma", "qual", "quais", "que", "com", "por", "para", "mais", "esta", "estao", "ser",
}  # fmt: skip


def _objetos_citados(texto: str) -> set[str]:
    """Ferramentas que trazem o dado citado no texto (vazio se nenhuma)."""
    alvo = _normalizar(texto)
    ferramentas: set[str] = set()
    for padrao, nomes in OBJETOS.items():
        if re.search(padrao, alvo):
            ferramentas |= nomes
    return ferramentas


def _palavras(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-z0-9-]+", _normalizar(texto)) if p not in PALAVRAS_VAZIAS}


def dado_faltante_valido(dado: str | None, mensagem: str) -> bool:
    """True só para dado que o engenheiro precisa trazer (fora do alcance das ferramentas)."""
    if not dado or not dado.strip():
        return False
    alvo = _normalizar(dado)
    if re.search(CAUSA, alvo) or _objetos_citados(dado):
        return False
    palavras, da_pergunta = _palavras(dado), _palavras(mensagem)
    return not (palavras and len(palavras & da_pergunta) / len(palavras) >= 0.6)


def sanear_nlu(nlu: AnaliseNLU | None, mensagem: str) -> AnaliseNLU | None:
    """Descarta o `dado_faltante` indevido do NLU; o resto da análise fica igual."""
    if (
        nlu is None
        or nlu.dado_faltante is None
        or dado_faltante_valido(nlu.dado_faltante, mensagem)
    ):
        return nlu
    return nlu.model_copy(update={"dado_faltante": None})


def acao_de_consulta(texto: str) -> bool:
    """True quando a "ação" só manda olhar dados (logs, métricas, deploys, wiki...)."""
    return bool(re.match(VERBOS_CONSULTA, _normalizar(texto))) and bool(_objetos_citados(texto))


def repete_consulta(texto: str, ferramentas_chamadas: set[str]) -> bool:
    """True quando o passo manda consultar um dado que uma ferramenta chamada já trouxe."""
    if not re.match(VERBOS_CONSULTA, _normalizar(texto)):
        return False
    return bool(_objetos_citados(texto) & set(ferramentas_chamadas))


def sanear_analise(analise: AnaliseIncidente, ferramentas_chamadas: set[str]) -> AnaliseIncidente:
    """Tira ações de consulta e próximos passos que repetem consultas já feitas."""
    acoes = [a for a in analise.acoes_sugeridas if not acao_de_consulta(a.acao)]
    passos = [p for p in analise.proximos_passos if not repete_consulta(p, ferramentas_chamadas)]
    if not passos:
        passos = [f"Avaliar e aprovar a ação sugerida: {a.acao}" for a in acoes[:2]]
    if not passos:
        passos = [f"Corrigir a causa principal: {analise.hipoteses[0].causa}"]
    return analise.model_copy(update={"acoes_sugeridas": acoes, "proximos_passos": passos})
