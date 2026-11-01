"""Pré-processamento do erro: limpa ruído e extrai a impressão digital."""
import re

from agente.schemas import ErroPreprocessado, ImpressaoDigital

LIMITE = 4000
SERVICOS = ("pedidos-api", "pagamentos-api", "estoque-worker", "auth-api")
_LIB_JAVA = ("java.", "javax.", "jdk.", "sun.", "org.springframework")
_FRAME_JAVA = re.compile(r"^\s*at\s+(?:[\w.$]+/)?([\w.$<>]+)\(.*\)\s*$")
_FRAME_PY = re.compile(r'^\s*File "([^"]+)", line \d+')
_LIB_PY = ("site-packages", "node_modules")
_EXCECAO = re.compile(r"\b(\w*(?:Exception|Error|Killed))\b")


def _tipo_frame(linha: str) -> str | None:
    """Devolve 'lib', 'app' ou None (linha que não é frame)."""
    m = _FRAME_JAVA.match(linha)
    if m:
        classe = linha.split("at ", 1)[1].lstrip()
        classe = classe.split("/", 1)[-1]
        return "lib" if classe.startswith(_LIB_JAVA) else "app"
    m = _FRAME_PY.match(linha)
    if m:
        return "lib" if any(p in m.group(1) for p in _LIB_PY) else "app"
    return None


def _limpar(texto: str) -> tuple[list[str], str | None]:
    """Remove frames de biblioteca e repetidos; devolve linhas e o primeiro frame da aplicação."""
    saida, primeiro, visto_app, pular_codigo = [], None, False, False
    for linha in texto.splitlines():
        if pular_codigo and not _FRAME_PY.match(linha) and linha.startswith((" ", "\t")):
            pular_codigo = False
            continue
        pular_codigo = False
        tipo = _tipo_frame(linha)
        if tipo is None:
            visto_app = False
            saida.append(linha)
        elif tipo == "lib":
            pular_codigo = bool(_FRAME_PY.match(linha))
        elif not visto_app:
            visto_app = True
            primeiro = primeiro or linha.strip().removeprefix("at ")
            saida.append(linha)
    return saida, primeiro


def preprocessar(texto: str, servico: str | None = None) -> ErroPreprocessado:
    """Limpa o stack trace, limita a 4.000 caracteres e extrai a impressão digital."""
    linhas, primeiro = _limpar(texto)
    limpo = "\n".join(linhas)[:LIMITE]
    m = _EXCECAO.search(limpo)
    achado = next((s for s in SERVICOS if s in texto), None)
    impressao = ImpressaoDigital(
        excecao=m.group(1) if m else None, primeiro_frame=primeiro, servico=servico or achado,
    )
    return ErroPreprocessado(impressao=impressao, texto_limpo=limpo)
