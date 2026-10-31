"""O sistema simulado: uma loja online com quatro serviços.

pedidos-api chama pagamentos-api e estoque-worker.
pagamentos-api chama o gateway externo PagaFácil.
auth-api valida tokens no provedor de identidade.
pedidos-api e estoque-worker usam o banco db-principal (pool máximo de 10 conexões).
"""

NAMESPACE = "Lab/Servicos"
GRUPO_DEPLOYS = "/lab/deploys"
GRUPO_ALARMES = "/lab/alarmes"
POOL_MAX = 10

SERVICOS = {
    "pedidos-api": {
        "versao": "3.2.0",
        "rotas": ["POST /pedidos", "GET /pedidos/{id}", "GET /pedidos"],
        "usa_db": True,
        "req_base": 140,
        "latencia_base": 180,
    },
    "pagamentos-api": {
        "versao": "2.13.4",
        "rotas": ["POST /pagamentos", "GET /pagamentos/{id}"],
        "usa_db": False,
        "req_base": 90,
        "latencia_base": 240,
    },
    "estoque-worker": {
        "versao": "1.5.2",
        "rotas": ["consumir fila estoque-reservas"],
        "usa_db": True,
        "req_base": 60,
        "latencia_base": 90,
    },
    "auth-api": {
        "versao": "1.7.9",
        "rotas": ["POST /token", "GET /me"],
        "usa_db": False,
        "req_base": 200,
        "latencia_base": 60,
    },
}

METRICAS = ["Requisicoes", "Erros5xx", "LatenciaP95", "MemoriaPct", "ConexoesDB"]

# Limites do detector de alarmes: métrica -> valor que dispara.
LIMITES = {
    "Erros5xx": 15,
    "LatenciaP95": 1500,
    "MemoriaPct": 90,
}


def grupo_logs(servico: str) -> str:
    return f"/lab/app/{servico}"
