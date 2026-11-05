"""Gera `dados/incidentes.db`, a base SQLite de serviços, deploys e incidentes (determinística)."""

import json
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO_PADRAO = RAIZ / "dados" / "incidentes.db"
CENARIOS = RAIZ / "dados_dummy" / "cenarios"

ESQUEMA_SQL = """
CREATE TABLE servicos (
    nome TEXT PRIMARY KEY, time TEXT NOT NULL, linguagem TEXT NOT NULL,
    banco TEXT, dependencia_externa TEXT
);
CREATE TABLE deploys (
    id INTEGER PRIMARY KEY, servico TEXT NOT NULL REFERENCES servicos(nome),
    versao TEXT NOT NULL, horario TEXT NOT NULL, autor TEXT NOT NULL, mudanca TEXT NOT NULL
);
CREATE TABLE incidentes (
    id INTEGER PRIMARY KEY, servico TEXT NOT NULL REFERENCES servicos(nome),
    inicio TEXT NOT NULL, fim TEXT NOT NULL, severidade TEXT NOT NULL,
    categoria TEXT NOT NULL, causa TEXT NOT NULL, cenario TEXT
);
"""

SERVICOS = [
    ("pedidos-api", "Loja", "Java", "db-principal", None),
    ("pagamentos-api", "Pagamentos", "Java", None, "PagaFácil"),
    ("estoque-worker", "Loja", "Python", "db-principal", None),
    ("auth-api", "Plataforma", "Go", None, None),
]

# (servico, versao, horario, autor, mudanca); os deploys dos cenários vêm dos JSON gravados.
DEPLOYS_ANTERIORES = [
    ("pedidos-api", "3.1.0", "2026-09-22T10:00:00-03:00", "Equipe Loja", "feat: filtro de pedidos"),
    (
        "pagamentos-api",
        "2.13.4",
        "2026-10-02T11:30:00-03:00",
        "ana.souza",
        "fix: arredonda centavos",
    ),
    ("estoque-worker", "1.5.2", "2026-09-30T15:00:00-03:00", "carlos.lima", "fix: log da reserva"),
    ("auth-api", "1.7.9", "2026-10-20T09:15:00-03:00", "beatriz.alves", "chore: atualiza deps"),
]

CAUSAS_CENARIO = {
    "pool_esgotado": ("pool_conexoes", "alta", "pool de conexões esgotado após a v3.2.0"),
    "banco_lento_com_deploy": (
        "banco_lento",
        "alta",
        "reindexação travou a tabela de estoque no db-principal",
    ),
    "deploy_com_bug": ("deploy_com_bug", "critica", "NullPointerException introduzido na v2.14.0"),
    "env_var_faltando": (
        "configuracao",
        "media",
        "variável ESTOQUE_QUEUE_URL ausente na v1.6.0",
    ),
    "certificado_expirado": ("certificado", "critica", "certificado TLS do idp expirou"),
    "vazamento_memoria": (
        "vazamento_memoria",
        "alta",
        "cache sem limite na v1.8.0 causou OOMKilled",
    ),
    "gateway_fora": ("dependencia_externa", "critica", "PagaFácil indisponível (503)"),
    "rate_limit": ("rate_limit", "media", "limite de 100 req/min do PagaFácil excedido (429)"),
}

# (servico, inicio, fim, severidade, categoria, causa)
HISTORICO = [
    (
        "pedidos-api",
        "2026-01-14T10:05",
        "2026-01-14T11:00",
        "alta",
        "pool_conexoes",
        "pool de conexões esgotado em pico de pedidos",
    ),
    (
        "pagamentos-api",
        "2026-01-27T19:40",
        "2026-01-27T20:30",
        "media",
        "rate_limit",
        "limite de requisições do PagaFácil excedido na Black Friday antecipada",
    ),
    (
        "estoque-worker",
        "2026-02-09T03:10",
        "2026-02-09T04:20",
        "media",
        "banco_lento",
        "consulta sem índice na tabela de reservas",
    ),
    (
        "auth-api",
        "2026-02-18T08:00",
        "2026-02-18T08:40",
        "alta",
        "deploy_com_bug",
        "deploy v1.6.2 quebrou a validação de refresh token",
    ),
    (
        "pedidos-api",
        "2026-03-05T14:20",
        "2026-03-05T15:10",
        "alta",
        "pool_conexoes",
        "vazamento de conexões em fluxo de cancelamento",
    ),
    (
        "pagamentos-api",
        "2026-03-19T22:00",
        "2026-03-19T23:15",
        "critica",
        "dependencia_externa",
        "PagaFácil fora do ar por manutenção não anunciada",
    ),
    (
        "estoque-worker",
        "2026-04-02T11:30",
        "2026-04-02T12:10",
        "baixa",
        "configuracao",
        "timeout da fila configurado com valor errado",
    ),
    (
        "auth-api",
        "2026-04-15T16:45",
        "2026-04-15T17:30",
        "media",
        "vazamento_memoria",
        "cache de sessões crescendo sem expiração",
    ),
    (
        "pedidos-api",
        "2026-05-07T09:10",
        "2026-05-07T09:50",
        "media",
        "deploy_com_bug",
        "deploy v3.0.3 com erro de serialização de pedidos",
    ),
    (
        "pagamentos-api",
        "2026-05-21T13:00",
        "2026-05-21T13:45",
        "media",
        "certificado",
        "certificado do cliente do PagaFácil expirou",
    ),
    (
        "estoque-worker",
        "2026-06-10T01:00",
        "2026-06-10T03:00",
        "alta",
        "banco_lento",
        "VACUUM manual bloqueou a tabela de estoque",
    ),
    (
        "auth-api",
        "2026-06-24T18:20",
        "2026-06-24T19:00",
        "alta",
        "dependencia_externa",
        "provedor de e-mail do código de verificação indisponível",
    ),
    (
        "pedidos-api",
        "2026-07-08T12:00",
        "2026-07-08T12:45",
        "media",
        "banco_lento",
        "relatório pesado concorrendo com o checkout no db-principal",
    ),
    (
        "pagamentos-api",
        "2026-08-03T15:30",
        "2026-08-03T16:10",
        "alta",
        "deploy_com_bug",
        "deploy v2.12.0 duplicou cobranças em retentativa",
    ),
    (
        "estoque-worker",
        "2026-08-26T07:45",
        "2026-08-26T08:30",
        "media",
        "vazamento_memoria",
        "lote de reservas mantido em memória causou OOMKilled",
    ),
    (
        "pedidos-api",
        "2026-09-11T17:10",
        "2026-09-11T18:00",
        "alta",
        "pool_conexoes",
        "pool de conexões esgotado por consultas lentas",
    ),
]


def _deploys_dos_cenarios() -> list[tuple]:
    deploys = []
    for arquivo in sorted(CENARIOS.glob("*.json")):
        for item in json.loads(arquivo.read_text(encoding="utf-8"))["deploys"]["deploys"]:
            deploys.append(
                (item["servico"], item["versao"], item["horario"], item["autor"], item["mensagem"])
            )
    return deploys


def _incidentes_dos_cenarios() -> list[tuple]:
    incidentes = []
    for arquivo in sorted(CENARIOS.glob("*.json")):
        cenario = json.loads(arquivo.read_text(encoding="utf-8"))["cenario"]
        categoria, severidade, causa = CAUSAS_CENARIO[cenario["id"]]
        incidentes.append(
            (
                cenario["servico"],
                cenario["sintoma_inicio"],
                cenario["janela"]["fim"],
                severidade,
                categoria,
                causa,
                cenario["id"],
            )
        )
    return incidentes


def construir(destino: Path | str = DESTINO_PADRAO) -> Path:
    """Recria o arquivo SQLite em `destino` e devolve o caminho."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.unlink(missing_ok=True)
    historico = [(*linha, None) for linha in HISTORICO]
    deploys = sorted(DEPLOYS_ANTERIORES + _deploys_dos_cenarios(), key=lambda d: d[2])
    incidentes = sorted(historico + _incidentes_dos_cenarios(), key=lambda i: i[1])
    with sqlite3.connect(destino) as conexao:
        conexao.executescript(ESQUEMA_SQL)
        conexao.executemany("INSERT INTO servicos VALUES (?,?,?,?,?)", SERVICOS)
        conexao.executemany(
            "INSERT INTO deploys (servico, versao, horario, autor, mudanca) VALUES (?,?,?,?,?)",
            deploys,
        )
        conexao.executemany(
            "INSERT INTO incidentes (servico, inicio, fim, severidade, categoria, causa, cenario)"
            " VALUES (?,?,?,?,?,?,?)",
            incidentes,
        )
    return destino


if __name__ == "__main__":
    print(f"Base gerada em {construir()}")
