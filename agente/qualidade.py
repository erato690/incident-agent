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
    r"\blogs?\b|\berros? nos logs\b|\bdependencias? externas?\b|\binfraestrutura\b": {
        "buscar_logs"
    },
    r"\bmetricas?\b|\b(volume|taxa|carga|pico) de requisic|\btaxa de erros?\b|\bcpu\b|"
    r"\blatencia\b|\bmemoria\b|\bdisco\b|\b(uso|consumo) (de|do|da)\b|\brecursos?\b": {
        "buscar_metricas"
    },
    r"\bdeploys?\b|\bimplantac": {"listar_deploys"},
    r"\bdiff\b|\bversoes\b|\bmudancas? (da|na|entre) vers": {"comparar_versoes"},
    r"\bwiki\b|\blimite documentado\b|\bdocumentac|\brunbooks?\b": {
        "consultar_wiki",
        "buscar_documentacao",
        "sugerir_acao",
    },
    r"\bestatisticas? do banco\b|\bestado (atual )?do banco\b|\bvarreduras?\b|\breindexac": {
        "consultar_estatisticas_banco"
    },
    r"\bhistorico de incidentes\b|\bincidentes anteriores\b": {
        "consultar_memoria",
        "consultar_sql",
    },
}
VERBOS_CONSULTA = (
    r"^(verifi|consult|chec|cheq|confer|confir|analis|investig|revis|examin|olh|busc|identific|"
    r"levant|avali|observ|acompanh|inspecion|monitor)\w*"
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


_PEDE_SERVICO = r"\bservicos?\b|\bqual (api|sistema|aplicac\w*|componente)\b"


def sanear_nlu(
    nlu: AnaliseNLU | None, mensagem: str, servico_sessao: str | None = None
) -> AnaliseNLU | None:
    """Descarta o `dado_faltante` indevido do NLU; o resto da análise fica igual.

    Sem serviço na mensagem, herda o que a conversa já nomeou. "Qual serviço?" sai sempre: o
    Investigador começa pela visão geral e só pergunta se as ferramentas não acharem nada."""
    if nlu is not None and not nlu.servico and servico_sessao:
        nlu = nlu.model_copy(update={"servico": servico_sessao})
    if (
        nlu is not None
        and nlu.dado_faltante
        and re.search(_PEDE_SERVICO, _normalizar(nlu.dado_faltante))
    ):
        return nlu.model_copy(update={"dado_faltante": None})
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


PREFIXO_LACUNA = "Lacuna: "
SEM_OBSERVACAO = (
    f"{PREFIXO_LACUNA}nenhuma ferramenta foi consultada neste turno; sem observação, a hipótese "
    "não se sustenta"
)
CONFIANCA_SEM_OBSERVACAO = 0.3


def sem_observacao(analise: AnaliseIncidente) -> AnaliseIncidente:
    """Análise sem nenhuma ferramenta chamada: nenhuma hipótese tem evidência (nem a de que "não
    há erro"); a confiança fica no máximo em 0,3 e a evidência inventada sai."""
    hipoteses = [
        hipotese.model_copy(
            update={
                "evidencia_insuficiente": True,
                "evidencia": None,
                "confianca": min(hipotese.confianca, CONFIANCA_SEM_OBSERVACAO),
                "dado_que_falta": SEM_OBSERVACAO,
            }
        )
        for hipotese in analise.hipoteses
    ]
    return analise.model_copy(update={"hipoteses": hipoteses})


def _como_lacuna(hipotese):
    """Dado que falta que as ferramentas alcançam (logs, métricas, uso de recurso...) não é
    pedido ao engenheiro: vira lacuna, dita como o que a investigação não trouxe."""
    dado = hipotese.dado_que_falta
    if not dado or dado.startswith(PREFIXO_LACUNA) or dado_faltante_valido(dado, ""):
        return hipotese
    texto = f"{PREFIXO_LACUNA}{dado} (as ferramentas consultadas não trouxeram esse dado)"
    return hipotese.model_copy(update={"dado_que_falta": texto})


def sanear_analise(analise: AnaliseIncidente, ferramentas_chamadas: set[str]) -> AnaliseIncidente:
    """Tira ações de consulta e próximos passos que repetem consultas já feitas; dado que falta
    ao alcance das ferramentas vira lacuna em vez de pergunta ao engenheiro."""
    # só a principal vira pergunta ao engenheiro; as secundárias dizem o que as confirmaria
    principal, *outras = analise.hipoteses
    analise = analise.model_copy(update={"hipoteses": [_como_lacuna(principal), *outras]})
    principal = analise.hipoteses[0]
    acoes = ordenar_e_filtrar_acoes(
        analise.acoes_sugeridas, principal.causa, principal.evidencia or ""
    )
    passos = [p for p in analise.proximos_passos if not repete_consulta(p, ferramentas_chamadas)]
    if not passos:
        passos = [f"Avaliar e aprovar a ação sugerida: {a.acao}" for a in acoes[:2]]
    if not passos:
        passos = [f"Corrigir a causa principal: {analise.hipoteses[0].causa}"]
    return analise.model_copy(update={"acoes_sugeridas": acoes, "proximos_passos": passos})


# --- Qualidade das ações sugeridas ---
# Ordem: primeiro a que desfaz a causa (rollback do deploy culpado, restaurar o valor anterior),
# depois a de menor risco, depois contenção. Ação condicional ("se o pico for legítimo") ou sem
# nenhum dado da evidência da hipótese principal sai. Risco alto só com evidência direta.

_VERSAO = r"\bv\d+(?:\.\d+)+\b"
_DE_PARA = r"([a-z_][\w.-]*)\s+de\s+(\d+(?:[.,]\d+)?)\s*(?:[a-z]+\s+)?para\s+(\d+(?:[.,]\d+)?)"
_CONDICIONAL = (
    r"(^|[\s,;(])(se|caso)\s+(o|a|os|as|for|forem|houver|necessari\w*|persist\w*|ainda|"
    r"continuar|o problema|nao)\b"
)
_DESFAZ = r"\b(rollback|revert\w*|restaur\w*|desfaz\w*|voltar)\b"
_MUDANCA_INTERNA = r"\b(deploy|versao|v\d+(?:\.\d+)+|diff|configurac\w*|reduziu|alterou|trocou)\b"
_ORDEM_RISCO = {"baixo": 0, "medio": 1, "alto": 2}


def dados_da_evidencia(texto: str) -> set[str]:
    """Dados citáveis da evidência: versões, números (2+ dígitos), chaves de configuração,
    cabeçalhos e termos em maiúsculas (ex.: REINDEX)."""
    texto = texto or ""
    dados = {v.casefold() for v in re.findall(_VERSAO, texto)}
    dados |= set(re.findall(r"(?<![\d.])\d{2,}(?![\d])", texto))
    dados |= {t.casefold() for t in re.findall(r"\b[a-z]+(?:_[a-z0-9]+)+\b", texto)}
    dados |= {t.casefold() for t in re.findall(r"\b[A-Z][\w]*(?:-[A-Z][\w]*)+\b", texto)}
    dados |= {t.casefold() for t in re.findall(r"\b[A-Z]{3,}\b", texto)}
    return dados


def _cita_dado(acao, dados: set[str]) -> bool:
    alvo = f"{acao.acao} {acao.motivo}".casefold()
    return any(re.search(rf"(?<![\w.]){re.escape(d)}(?![\w])", alvo) for d in dados)


def acao_condicional(acao) -> bool:
    """True para ação hipotética ("se necessário", "caso persista", "se o pico for legítimo")."""
    return bool(re.search(_CONDICIONAL, _normalizar(f"{acao.acao}. {acao.motivo}")))


def _acao_de_desfazer(causa: str, evidencia: str):
    """Ação determinística que desfaz a causa interna (valor anterior do diff ou rollback)."""
    from agente.schemas import AcaoSugerida

    texto = f"{causa} {evidencia}"
    versoes = re.findall(_VERSAO, texto)
    versao = versoes[0] if versoes else None
    de_para = re.search(_DE_PARA, texto)
    if de_para:
        chave, antigo, novo = de_para.groups()
        sufixo = f" (valor anterior à {versao})" if versao else ""
        onde = f" na {versao}" if versao else ""
        return AcaoSugerida(
            acao=f"Restaurar {chave} para {antigo}{sufixo}",
            motivo=f"A evidência mostra {chave} de {antigo} para {novo}{onde}; voltar ao valor "
            "anterior desfaz a causa.",
            risco="baixo",
        )
    if versao:
        return AcaoSugerida(
            acao=f"Fazer rollback da {versao}",
            motivo=f"A {versao} é a mudança apontada como causa na evidência; o rollback a desfaz.",
            risco="medio",
        )
    return None


def _termos(acao) -> set[str]:
    palavras = re.findall(r"[a-z0-9.]+", _normalizar(acao.acao))
    return {p.removeprefix("v") for p in palavras if p not in PALAVRAS_VAZIAS and len(p) > 1}


def _sem_quase_repetidas(acoes: list, dados: set[str]) -> list:
    """Duas ações quase iguais (uma contém a outra ou 60% dos termos em comum): fica a que cita
    mais dados da evidência (a mais específica)."""
    escolhidas: list = []
    for acao in acoes:
        termos = _termos(acao)
        repetida = None
        for i, outra in enumerate(escolhidas):
            comuns = termos & _termos(outra)
            menor = min(len(termos), len(_termos(outra))) or 1
            mesmo_verbo = _primeira(acao) == _primeira(outra)
            if len(comuns) / menor >= (0.5 if mesmo_verbo else 0.6):
                repetida = i
                break
        if repetida is None:
            escolhidas.append(acao)
        elif _peso(acao, dados) > _peso(escolhidas[repetida], dados):
            escolhidas[repetida] = acao
    return escolhidas


def _primeira(acao) -> str:
    palavras = _normalizar(acao.acao).split()
    return palavras[0] if palavras else ""


def _inventa_valor(acao, de_para) -> bool:
    """A ação põe na chave do diff um número que não é o valor anterior (ex.: pool 15 quando o
    diff mostra pool_max de 20 para 10): restaurar o anterior vem antes de inventar outro."""
    if not de_para:
        return False
    chave, antigo, _ = de_para.groups()
    raiz = chave.split("_")[0].casefold()
    texto = _normalizar(acao.acao)
    if raiz not in texto:
        return False
    numeros = set(re.findall(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w.])", texto))
    return bool(numeros) and antigo not in numeros


def _peso(acao, dados: set[str]) -> int:
    alvo = f"{acao.acao} {acao.motivo}".casefold()
    citados = sum(1 for d in dados if re.search(rf"(?<![\w.]){re.escape(d)}(?![\w])", alvo))
    return citados * 10 + len(re.findall(_VERSAO + r"|\d+", acao.acao))


def ordenar_e_filtrar_acoes(acoes: list, causa: str, evidencia: str) -> list:
    """Filtra e ordena as ações pela evidência da hipótese principal (no máximo 3)."""
    dados = dados_da_evidencia(f"{causa} {evidencia}")
    de_para = re.search(_DE_PARA, f"{causa} {evidencia}")
    candidatas = [
        a
        for a in acoes
        if not (acao_de_consulta(a.acao) or acao_condicional(a) or _inventa_valor(a, de_para))
    ]
    boas = [a for a in candidatas if dados and _cita_dado(a, dados)]
    if not boas:
        # nenhuma cita dado: fica a de menor risco que sobra (risco alto exige evidência direta)
        boas = sorted(
            (a for a in candidatas if a.risco != "alto"), key=lambda a: _ORDEM_RISCO[a.risco]
        )[:1]
    boas = _sem_quase_repetidas(boas, dados)
    interna = re.search(_MUDANCA_INTERNA, _normalizar(causa))
    desfaz = [a for a in boas if re.search(_DESFAZ, _normalizar(a.acao))]
    if interna and not desfaz:
        nova = _acao_de_desfazer(causa, evidencia)
        if nova is not None:
            boas.insert(0, nova)
    boas.sort(
        key=lambda a: (0 if re.search(_DESFAZ, _normalizar(a.acao)) else 1, _ORDEM_RISCO[a.risco])
    )
    return boas[:3]
