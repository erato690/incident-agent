"""Fonte de dados da loja (logs, métricas, deploys e estatísticas do banco) e resumos.

Segue o contrato 1.1.0 do `incident-shop` (`docs/contrato-api.md`; a rota
`/estatisticas_banco` é o acréscimo da 1.1.0, em `specs/004-*/contracts/`). Duas fontes, mesma
interface:

- `FonteLoja.ao_vivo(url, cenario)`: `GET /logs`, `/metricas`, `/deploys` e
  `/estatisticas_banco` com `cenario`, `servico`, `nivel`, `metrica` e `limite` na query.
- `FonteLoja.gravada(cenario)`: lê `dados_dummy/cenarios/<id>.json`, gravado por
  `scripts/gravar_cenarios.py` no formato
  `{"cenario": <item de GET /cenarios>, "logs": <corpo de GET /logs>,
    "metricas": <corpo de GET /metricas>, "deploys": <corpo de GET /deploys>,
    "estatisticas_banco": <corpo de GET /estatisticas_banco sem `servico`, todas as tabelas>}`
  e filtra localmente por serviço, nível e métrica.

O cenário é configuração da fonte: o modelo nunca o vê nem o informa.
"""

import json
import os
import re
from collections import defaultdict
from pathlib import Path

import httpx

RAIZ_PADRAO = Path(__file__).resolve().parent.parent / "dados_dummy" / "cenarios"
MAX_GRUPOS = 10
LIMITE_LOGS = 500
TIMEOUT_S = 5.0
METRICAS = (
    "requisicoes",
    "erros_5xx",
    "latencia_p95",
    "cpu",
    "memoria",
    "reinicios",
    "conexoes_db",
    "fila_mensagens",
)
# Tags do incident-shop (`git tag` do repositório, em ordem de lançamento por serviço). O
# JSON gravado só tem os deploys da janela do cenário; daqui sai a versão anterior.
TAGS_CONHECIDAS = (
    "pedidos-api/v3.1.0",
    "pedidos-api/v3.2.0",
    "pedidos-api/v3.2.1",
    "pagamentos-api/v2.13.4",
    "pagamentos-api/v2.14.0",
    "estoque-worker/v1.5.2",
    "estoque-worker/v1.6.0",
    "auth-api/v1.7.9",
    "auth-api/v1.8.0",
)


class ErroLoja(RuntimeError):  # noqa: N818 - nome de domínio em português
    """Falha ao consultar a loja, com mensagem legível para o modelo."""


class FonteLoja:
    """Logs, métricas e deploys de um cenário, filtrados por serviço, nível e métrica."""

    def __init__(
        self,
        dados: dict | None = None,
        *,
        url: str | None = None,
        cenario: str | None = None,
        cliente: httpx.Client | None = None,
    ):
        self._dados = dados
        self._cliente = cliente
        self._url = url.rstrip("/") if url else None
        self.cenario: str = cenario or (dados["cenario"]["id"] if dados else "")

    @classmethod
    def gravada(cls, cenario: str, raiz: Path | str = RAIZ_PADRAO) -> "FonteLoja":
        """Lê `<raiz>/<cenario>.json` (formato descrito no topo do módulo)."""
        caminho = Path(raiz) / f"{cenario}.json"
        if not caminho.exists():
            raise FileNotFoundError(f"Cenário gravado inexistente: {caminho}")
        return cls(json.loads(caminho.read_text(encoding="utf-8")), cenario=cenario)

    @classmethod
    def ao_vivo(cls, url: str, cenario: str, cliente: httpx.Client | None = None) -> "FonteLoja":
        """Consulta a API da loja; `cliente` permite injetar transporte (testes)."""
        return cls(url=url, cenario=cenario, cliente=cliente or httpx.Client(timeout=TIMEOUT_S))

    def _get(self, rota: str, *, com_cenario: bool = True, **params) -> dict:
        params = {chave: valor for chave, valor in params.items() if valor is not None}
        if com_cenario:
            params = {"cenario": self.cenario, **params}
        try:
            resposta = self._cliente.get(f"{self._url}{rota}", params=params)
        except httpx.HTTPError as erro:
            raise ErroLoja(f"Store unavailable at {rota}: {erro}") from erro
        if resposta.status_code in (404, 422):
            raise ErroLoja(
                f"Store rejected the query {rota} ({resposta.status_code}): "
                f"{resposta.json().get('detail')}"
            )
        resposta.raise_for_status()
        return resposta.json()

    def logs(self, servico: str, nivel: str | None = None) -> dict:
        """Corpo de `/logs`: `{"total", "truncado", "logs": [...]}`."""
        nivel = nivel.upper() if nivel else None
        if self._url:
            corpo = self._get("/logs", servico=servico, nivel=nivel, limite=LIMITE_LOGS)
            return {campo: corpo[campo] for campo in ("total", "truncado", "logs")}
        itens = [
            registro
            for registro in self._dados["logs"]["logs"]
            if registro["servico"] == servico and (nivel is None or registro["nivel"] == nivel)
        ]
        return {"total": len(itens), "truncado": False, "logs": itens}

    def metricas(self, servico: str, metrica: str | None = None) -> list[dict]:
        """Séries de `/metricas` (com `unidade` e `resumo`)."""
        if self._url:
            return self._get("/metricas", servico=servico, metrica=metrica)["series"]
        if metrica is not None and metrica not in METRICAS:
            raise ErroLoja(f"Unknown metric: {metrica}. Use one of {', '.join(METRICAS)}.")
        return [
            serie
            for serie in self._dados["metricas"]["series"]
            if serie["servico"] == servico and (metrica is None or serie["metrica"] == metrica)
        ]

    def deploys(self, servico: str | None = None) -> list[dict]:
        """Deploys de `/deploys`, em ordem crescente de horário."""
        if self._url:
            return self._get("/deploys", servico=servico)["deploys"]
        return [
            deploy
            for deploy in self._dados["deploys"]["deploys"]
            if servico is None or deploy["servico"] == servico
        ]

    def estatisticas_banco(self, servico: str) -> dict:
        """Corpo de `/estatisticas_banco`; serviço sem banco devolve `tabelas: []`.

        Gravada: a chave `estatisticas_banco` traz todas as tabelas (corpo sem `servico`);
        aqui ficam só as tabelas cujo `servicos` contém o serviço.
        """
        if self._url:
            return self._get("/estatisticas_banco", servico=servico)
        corpo = self._dados.get("estatisticas_banco") or {}
        consulta = {"cenario": self.cenario, "momento": None, **corpo.get("consulta", {})}
        return {
            "consulta": {**consulta, "servico": servico},
            "banco": corpo.get("banco"),
            "tabelas": [t for t in corpo.get("tabelas", []) if servico in t["servicos"]],
        }

    def tags_do_servico(self) -> list[str]:
        """Todas as tags já lançadas, da mais antiga à mais nova (sem janela de cenário).

        Ao vivo: `GET /deploys` sem janela. Gravada: `TAGS_CONHECIDAS`. Se a consulta falhar,
        devolve lista vazia e o resumo apenas omite a versão anterior.
        """
        if not self._url:
            return list(TAGS_CONHECIDAS)
        try:
            corpo = self._get("/deploys", com_cenario=False)["deploys"]
        except (ErroLoja, httpx.HTTPError):
            return []
        return [deploy["tag"] for deploy in sorted(corpo, key=lambda item: item["horario"])]


def fonte_padrao(cenario: str, raiz: Path | str = RAIZ_PADRAO) -> FonteLoja:
    """Ao vivo se `LOJA_URL` estiver definida; senão, a gravada do cenário."""
    url = os.environ.get("LOJA_URL")
    return FonteLoja.ao_vivo(url, cenario) if url else FonteLoja.gravada(cenario, raiz)


def _hora(horario: str) -> str:
    """Parte HH:MM:SS de um horário ISO."""
    return horario.split("T")[-1][:8]


def _linha(mensagem: str, limite: int = 300) -> str:
    """Mensagem em uma linha (primeiras linhas do stack), cortada em `limite`."""
    texto = " | ".join(linha.strip() for linha in mensagem.splitlines()[:3] if linha.strip())
    return texto if len(texto) <= limite else texto[:limite] + "..."


_NIVEL_PESO = {"ERROR": 0, "WARN": 1, "INFO": 2}


def _chave(mensagem: str) -> str:
    """Mensagem sem números: agrupa linhas que só diferem em valores (ex.: heap 85% e 86%)."""
    return re.sub(r"\d+(?:[.,]\d+)?", "#", _linha(mensagem))


def resumir_logs(resultado: dict, max_grupos: int = MAX_GRUPOS) -> str:
    """Agrupa por (serviço, nível, mensagem sem números) com contagem e primeiro/último horário.

    Mostra o exemplo mais recente de cada grupo. Quando há grupos demais, os de ERROR e WARN
    vêm antes dos de INFO, para nenhum erro ficar escondido entre os omitidos.
    """
    logs = resultado["logs"]
    if not logs:
        return "No logs found."
    grupos: dict[tuple, list[dict]] = defaultdict(list)
    for registro in sorted(logs, key=lambda item: item["horario"]):
        chave = (registro["servico"], registro["nivel"], _chave(registro["mensagem"]))
        grupos[chave].append(registro)
    ordem = sorted(
        grupos.items(),
        key=lambda grupo: (_NIVEL_PESO.get(grupo[0][1], 3), grupo[1][0]["horario"]),
    )
    escolhidos = sorted(ordem[:max_grupos], key=lambda grupo: grupo[1][0]["horario"])
    cabecalho = (
        f"Logs: total {resultado['total']}, truncated: {'yes' if resultado['truncado'] else 'no'}"
    )
    linhas = [cabecalho] + [
        f"[{nivel}] {servico}: {_linha(itens[-1]['mensagem'])} "
        f"(x{len(itens)}, {_hora(itens[0]['horario'])} a {_hora(itens[-1]['horario'])})"
        for (servico, nivel, _), itens in escolhidos
    ]
    if len(grupos) > max_grupos:
        linhas.append(f"... {len(grupos) - max_grupos} groups omitted (INFO level first)")
    return "\n".join(linhas)


def resumir_metricas(series: list[dict]) -> str:
    """Por série: mínimo, máximo, média e último valor, com a unidade."""
    if not series:
        return "No metrics found."
    linhas = []
    for serie in series:
        resumo = serie["resumo"]
        linhas.append(
            f"{serie['servico']} {serie['metrica']} ({serie['unidade']}): min {resumo['min']}, "
            f"max {resumo['max']}, avg {resumo['media']}, last {resumo['ultimo']}"
        )
    return "\n".join(linhas)


def _anterior(tag: str, tags: list[str]) -> str | None:
    """Tag anterior do mesmo serviço em `tags` (ordem de lançamento), se existir."""
    servico = tag.split("/")[0]
    do_servico = [outra for outra in tags if outra.split("/")[0] == servico]
    posicao = do_servico.index(tag) if tag in do_servico else 0
    return do_servico[posicao - 1] if posicao > 0 else None


def resumir_deploys(deploys: list[dict], tags: list[str] | None = None) -> str:
    """Lista curta de deploys, do mais recente para o mais antigo.

    Com `tags` (histórico completo, de `FonteLoja.tags_do_servico`), cada linha informa a
    tag anterior do mesmo serviço, ex.: "pedidos-api/v3.2.1 (anterior: pedidos-api/v3.2.0)".
    """
    if not deploys:
        return "No deploys found."
    linhas = []
    for deploy in sorted(deploys, key=lambda item: item["horario"], reverse=True):
        anterior = _anterior(deploy["tag"], tags or [])
        sufixo = f" (previous: {anterior})" if anterior else ""
        linhas.append(
            f"{deploy['horario']} {deploy['tag']}{sufixo} (commit {deploy['commit']}, "
            f"author {deploy['autor']}): {deploy['mensagem']}"
        )
    return "\n".join(linhas)


def _linha_tabela(tabela: dict) -> list[str]:
    """Uma tabela em uma linha; manutenção em andamento vem destacada em outra."""
    linhas = [
        f"{tabela['tabela']}: varreduras seq {tabela['varreduras_sequenciais']} x índice "
        f"{tabela['varreduras_por_indice']}, último ANALYZE {tabela['ultimo_analyze']}, "
        f"inchaço de índices {tabela['inchaco_indice_pct']}%, reindexação em andamento: "
        f"{'sim' if tabela['reindexacao_em_andamento'] else 'não'}"
    ]
    operacao = tabela["operacao_em_andamento"]
    if operacao or tabela["reindexacao_em_andamento"]:
        linhas.append(
            f"MANUTENÇÃO EM ANDAMENTO: {operacao or 'REINDEX'} na tabela {tabela['tabela']}"
        )
    return linhas


def resumir_estatisticas(resultado: dict) -> str:
    """Texto compacto por tabela das estatísticas do banco do serviço."""
    servico = resultado["consulta"]["servico"]
    if not resultado["tabelas"]:
        return f"Sem estatísticas de banco para {servico} (o serviço não usa o db-principal)."
    cabecalho = (
        f"Banco {resultado['banco']} ({servico}), retrato de {resultado['consulta']['momento']}"
    )
    linhas = [linha for tabela in resultado["tabelas"] for linha in _linha_tabela(tabela)]
    return "\n".join([cabecalho, *linhas])
