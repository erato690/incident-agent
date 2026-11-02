"""Comparação de versões pela API REST pública do GitHub, com reserva gravada.

Limitação: sem GITHUB_TOKEN, a API do GitHub aceita 60 chamadas por hora. Quando o limite
estoura (403), usa a resposta gravada e o log mostra o 403 e a hora de reset. Para chamada ao
vivo, defina GITHUB_TOKEN (token pessoal só com leitura pública basta).

Rota usada: GET /repos/erato690/incident-shop/compare/{base}...{nova}. As tags têm barra
(`servico/vX.Y.Z`) e a API aceita a barra literal nesse caminho, então não se codifica.
Sem rede, com limite de requisições (403/429) ou erro do servidor, lê a gravação em
`dados_dummy/github/` (nome do arquivo com "/" trocado por "__") e marca `reserva=True`.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import httpx
from pydantic import BaseModel

from agente.mascara import mascarar

REPO = "erato690/incident-shop"
URL = f"https://api.github.com/repos/{REPO}/compare/{{base}}...{{nova}}"
RAIZ_RESERVA = Path(__file__).resolve().parent.parent / "dados_dummy" / "github"
LOG = logging.getLogger(__name__)
PREFIXO_MOTIVO = "Fallback reason: "
MARCA_RESERVA = "[RECORDED FALLBACK: saved response, not queried now]"
MAX_COMMITS, MAX_ARQUIVOS, MAX_TRECHO = 10, 10, 800


class ErroComparacao(Exception):  # noqa: N818 - nome de domínio em português
    """Falha legível ao comparar versões."""


class Commit(BaseModel):
    mensagem: str
    autor: str
    data: str


class Arquivo(BaseModel):
    nome: str
    status: str
    adicoes: int
    remocoes: int
    trecho: str


class ComparacaoVersoes(BaseModel):
    base: str
    nova: str
    commits: list[Commit]
    arquivos: list[Arquivo]
    reserva: bool = False
    motivo_reserva: str | None = None


def nome_reserva(base: str, nova: str) -> str:
    """Nome de arquivo seguro: a barra das tags vira "__"."""
    return f"{base}...{nova}.json".replace("/", "__")


def _converter(
    base: str, nova: str, bruto: dict, reserva: bool, motivo: str | None = None
) -> ComparacaoVersoes:
    commits = [
        Commit(
            mensagem=item["commit"]["message"].splitlines()[0],
            autor=item["commit"]["author"]["name"],
            data=item["commit"]["author"]["date"],
        )
        for item in bruto.get("commits", [])[:MAX_COMMITS]
    ]
    arquivos = [
        Arquivo(
            nome=item["filename"],
            status=item["status"],
            adicoes=item["additions"],
            remocoes=item["deletions"],
            trecho=item.get("patch", "")[:MAX_TRECHO],
        )
        for item in bruto.get("files", [])[:MAX_ARQUIVOS]
    ]
    return ComparacaoVersoes(
        base=base,
        nova=nova,
        commits=commits,
        arquivos=arquivos,
        reserva=reserva,
        motivo_reserva=motivo,
    )


def _cabecalhos() -> dict:
    token = os.getenv("GITHUB_TOKEN")
    cabecalhos = {"Accept": "application/vnd.github+json"}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    return cabecalhos


def descrever_falha(erro: httpx.HTTPError) -> str:
    """Motivo legível da falha: limite de requisições, status HTTP ou falta de rede."""
    if not isinstance(erro, httpx.HTTPStatusError):
        return f"no network: {type(erro).__name__}: {erro}"
    resposta = erro.response
    cabecalhos = resposta.headers
    if resposta.status_code in (403, 429) and cabecalhos.get("x-ratelimit-remaining") == "0":
        limite = cabecalhos.get("x-ratelimit-limit", "?")
        sem_token = " without token" if "Authorization" not in erro.request.headers else ""
        reset = cabecalhos.get("x-ratelimit-reset")
        hora = f", resets at {datetime.fromtimestamp(int(reset)):%H:%M}" if reset else ""
        return (
            f"GitHub limit of {limite} req/h{sem_token} exhausted (x-ratelimit-remaining=0{hora})"
        )
    return f"GitHub responded {resposta.status_code}"


def _ler_reserva(base: str, nova: str, raiz: Path, motivo: str) -> ComparacaoVersoes:
    caminho = Path(raiz) / nome_reserva(base, nova)
    if not caminho.exists():
        raise ErroComparacao(
            f"GitHub unavailable ({motivo}) and no recorded fallback for {base} and {nova}."
        )
    LOG.warning("comparar_versoes %s...%s: reserva gravada: %s", base, nova, motivo)
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    return _converter(base, nova, bruto, True, motivo)


def buscar_bruto(base: str, nova: str, cliente: httpx.Client) -> dict:
    """Resposta crua da API (usada também para gravar a reserva)."""
    resposta = cliente.get(URL.format(base=base, nova=nova), headers=_cabecalhos(), timeout=10.0)
    if resposta.status_code == 404:
        raise ErroComparacao(f"Version not found on GitHub: {base} or {nova}.")
    resposta.raise_for_status()
    return resposta.json()


def comparar_versoes(
    base: str,
    nova: str,
    cliente: httpx.Client | None = None,
    raiz_reserva: Path | str = RAIZ_RESERVA,
) -> ComparacaoVersoes:
    """Compara duas tags; usa a reserva gravada em falha de rede, limite ou erro do servidor."""
    cliente = cliente or httpx.Client()
    try:
        return _converter(base, nova, buscar_bruto(base, nova, cliente), False)
    except httpx.HTTPError as erro:
        return _ler_reserva(base, nova, Path(raiz_reserva), descrever_falha(erro))


def gravar_comparacao(base: str, nova: str, cliente: httpx.Client, raiz: Path | str) -> Path:
    """Grava só commits e arquivos da resposta, para uso como reserva."""
    bruto = buscar_bruto(base, nova, cliente)
    recorte = {
        "total_commits": bruto.get("total_commits"),
        "commits": bruto.get("commits", []),
        "files": bruto.get("files", []),
    }
    caminho = Path(raiz) / nome_reserva(base, nova)
    caminho.write_text(json.dumps(recorte, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def resumir_comparacao(comparacao: ComparacaoVersoes) -> str:
    """Texto curto para o modelo: commits, arquivos e trechos do diff."""
    linhas = [f"Comparison {comparacao.base} -> {comparacao.nova}"] + (
        [MARCA_RESERVA, f"{PREFIXO_MOTIVO}{comparacao.motivo_reserva}"]
        if comparacao.reserva
        else []
    )
    linhas += [
        f"commit: {commit.mensagem} ({commit.autor}, {commit.data})"
        for commit in comparacao.commits
    ]
    for arquivo in comparacao.arquivos:
        linhas.append(
            f"file: {arquivo.nome} [{arquivo.status}, +{arquivo.adicoes}/-{arquivo.remocoes}]"
        )
        if arquivo.trecho:
            linhas.append(arquivo.trecho)
    return mascarar("\n".join(linhas))
