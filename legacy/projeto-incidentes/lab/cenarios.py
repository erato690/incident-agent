"""Catálogo de falhas que o laboratório injeta no sistema.

Cada cenário tem uma causa raiz conhecida (o gabarito). O agente nunca vê o gabarito:
ele só enxerga logs, métricas, deploys e alarmes, como numa produção de verdade.
"""

from dataclasses import dataclass, field
from random import Random
from typing import Callable


@dataclass
class Efeito:
    """O que um cenário produz em um minuto do incidente."""

    logs: list[tuple[str, str, str]] = field(default_factory=list)  # (servico, nivel, mensagem)
    metricas: dict[tuple[str, str], float] = field(default_factory=dict)  # (servico, metrica) -> valor


@dataclass
class Deploy:
    servico: str
    versao: str
    commit: str
    autor: str
    mudanca: str
    minutos_antes: int = 3  # quanto tempo antes do início dos sintomas o deploy acontece


@dataclass
class Cenario:
    id: str
    titulo: str
    servico: str
    categoria: str
    causa_raiz: str
    duracao: int  # minutos
    efeito: Callable[[int, int, Random], Efeito]
    deploy: Deploy | None = None


def _deploy_com_bug(t, dur, rng):
    e = Efeito()
    for _ in range(rng.randint(8, 20)):
        e.logs.append((
            "pagamentos-api", "ERROR",
            "java.lang.NullPointerException: Cannot invoke \"Cupom.getDesconto()\" because \"cupom\" is null\n"
            "\tat br.loja.pagamentos.PagamentoService.confirmar(PagamentoService.java:88)\n"
            "\tat br.loja.pagamentos.PagamentoController.post(PagamentoController.java:41)",
        ))
    e.metricas[("pagamentos-api", "Erros5xx")] = rng.randint(25, 45)
    e.logs.append(("pedidos-api", "WARN", "pagamentos-api respondeu 500 em POST /pagamentos, pedido marcado como PENDENTE"))
    return e


def _pool_esgotado(t, dur, rng):
    e = Efeito()
    pico = 1.0 + min(t, 10) / 10  # o tráfego dobra nos primeiros 10 minutos
    e.metricas[("pedidos-api", "Requisicoes")] = 140 * pico * 1.4
    e.metricas[("pedidos-api", "ConexoesDB")] = 10
    e.metricas[("pedidos-api", "LatenciaP95")] = rng.randint(2500, 5200)
    e.metricas[("pedidos-api", "Erros5xx")] = rng.randint(18, 40)
    for _ in range(rng.randint(5, 15)):
        e.logs.append((
            "pedidos-api", "ERROR",
            "HikariPool-1 - Connection is not available, request timed out after 3000ms (total=10, active=10, idle=0, waiting=37)",
        ))
    return e


def _env_var_faltando(t, dur, rng):
    e = Efeito()
    e.metricas[("estoque-worker", "Requisicoes")] = 0
    e.logs.append(("estoque-worker", "ERROR",
                   "Traceback (most recent call last):\n"
                   "  File \"/app/worker/config.py\", line 12, in <module>\n"
                   "    QUEUE_URL = os.environ[\"ESTOQUE_QUEUE_URL\"]\n"
                   "KeyError: 'ESTOQUE_QUEUE_URL'"))
    e.logs.append(("estoque-worker", "INFO", "container estoque-worker reiniciado (restart #%d, motivo: Error, exit code 1)" % (t + 1)))
    if t > 4:
        e.logs.append(("pedidos-api", "WARN", "fila estoque-reservas com %d mensagens acumuladas" % (t * 120)))
    return e


def _gateway_fora(t, dur, rng):
    e = Efeito()
    for _ in range(rng.randint(6, 14)):
        e.logs.append(("pagamentos-api", "ERROR",
                       "Falha ao chamar https://api.pagafacil.com.br/v2/cobrancas: HTTP 503 Service Unavailable (tentativa 3/3)"))
    e.metricas[("pagamentos-api", "Erros5xx")] = rng.randint(20, 35)
    e.metricas[("pagamentos-api", "LatenciaP95")] = rng.randint(3000, 9000)
    return e


def _vazamento_memoria(t, dur, rng):
    e = Efeito()
    ciclo = t % 12  # a memória sobe por 12 minutos, o pod morre e recomeça
    mem = 55 + ciclo * 4
    e.metricas[("auth-api", "MemoriaPct")] = min(mem, 99)
    if ciclo == 11:
        e.logs.append(("auth-api", "ERROR", "container auth-api terminado: OOMKilled (limite 512Mi)"))
        e.metricas[("auth-api", "Erros5xx")] = rng.randint(30, 60)
    elif ciclo > 7:
        e.logs.append(("auth-api", "WARN", "GC overhead alto: 41% do tempo em coleta, heap usado %d%%" % mem))
        e.metricas[("auth-api", "LatenciaP95")] = rng.randint(900, 2000)
    return e


def _certificado_expirado(t, dur, rng):
    e = Efeito()
    for _ in range(rng.randint(10, 25)):
        e.logs.append(("auth-api", "ERROR",
                       "Erro ao buscar JWKS em https://idp.loja.internal/.well-known/jwks.json: "
                       "SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired'))"))
    e.metricas[("auth-api", "Erros5xx")] = rng.randint(40, 80)
    e.logs.append(("pedidos-api", "WARN", "auth-api retornou 500 ao validar token, requisição negada"))
    return e


def _rate_limit(t, dur, rng):
    e = Efeito()
    e.metricas[("pagamentos-api", "Requisicoes")] = 90 * 2.5
    for _ in range(rng.randint(4, 10)):
        e.logs.append(("pagamentos-api", "WARN",
                       "PagaFácil respondeu 429 Too Many Requests (X-RateLimit-Limit: 100/min, Retry-After: 30)"))
    e.metricas[("pagamentos-api", "Erros5xx")] = rng.randint(16, 28)
    return e


def _banco_lento_com_deploy(t, dur, rng):
    e = Efeito()
    for servico in ("pedidos-api", "estoque-worker"):
        for _ in range(rng.randint(3, 8)):
            e.logs.append((servico, "ERROR",
                           "org.postgresql.util.PSQLException: ERROR: canceling statement due to statement timeout "
                           "(query: UPDATE estoque SET reservado = reservado + $1 WHERE sku = $2)"))
        e.metricas[(servico, "LatenciaP95")] = rng.randint(2000, 6000)
        e.metricas[(servico, "Erros5xx")] = rng.randint(15, 30)
    e.logs.append(("estoque-worker", "WARN", "lock wait na tabela estoque há %ds (processo de reindexação noturna ativo)" % (30 + t * 60)))
    return e


CENARIOS: dict[str, Cenario] = {c.id: c for c in [
    Cenario(
        id="deploy_com_bug", titulo="NullPointerException após deploy", servico="pagamentos-api",
        categoria="bug_de_codigo", duracao=25, efeito=_deploy_com_bug,
        causa_raiz="O deploy v2.14.0 do pagamentos-api introduziu um NullPointerException ao confirmar pagamento sem cupom.",
        deploy=Deploy("pagamentos-api", "2.14.0", "a1f3c9e", "ana.souza", "Aplica desconto de cupom na confirmação do pagamento"),
    ),
    Cenario(
        id="pool_esgotado", titulo="Pool de conexões esgotado no pico", servico="pedidos-api",
        categoria="capacidade", duracao=30, efeito=_pool_esgotado,
        causa_raiz="Pico de tráfego no pedidos-api esgotou o pool de conexões com o banco (máximo 10).",
    ),
    Cenario(
        id="env_var_faltando", titulo="Variável de ambiente ausente", servico="estoque-worker",
        categoria="configuracao", duracao=20, efeito=_env_var_faltando,
        causa_raiz="O deploy v1.6.0 do estoque-worker passou a exigir ESTOQUE_QUEUE_URL, que não foi configurada no ambiente.",
        deploy=Deploy("estoque-worker", "1.6.0", "7bd0e21", "carlos.lima", "Lê a URL da fila de uma variável de ambiente", minutos_antes=1),
    ),
    Cenario(
        id="gateway_fora", titulo="Gateway de pagamento indisponível", servico="pagamentos-api",
        categoria="dependencia_externa", duracao=35, efeito=_gateway_fora,
        causa_raiz="O gateway externo PagaFácil ficou indisponível (HTTP 503). Nenhuma mudança no código.",
    ),
    Cenario(
        id="vazamento_memoria", titulo="Vazamento de memória com OOMKilled", servico="auth-api",
        categoria="bug_de_codigo", duracao=48, efeito=_vazamento_memoria,
        causa_raiz="O deploy v1.8.0 do auth-api introduziu um cache sem limite que vaza memória até o pod ser morto (OOMKilled).",
        deploy=Deploy("auth-api", "1.8.0", "c44e8b0", "beatriz.alves", "Cache em memória para tokens validados", minutos_antes=40),
    ),
    Cenario(
        id="certificado_expirado", titulo="Certificado TLS expirado", servico="auth-api",
        categoria="configuracao", duracao=30, efeito=_certificado_expirado,
        causa_raiz="O certificado TLS do provedor de identidade (idp.loja.internal) expirou e o auth-api não consegue validar tokens.",
    ),
    Cenario(
        id="rate_limit", titulo="Rate limit no gateway de pagamento", servico="pagamentos-api",
        categoria="dependencia_externa", duracao=20, efeito=_rate_limit,
        causa_raiz="O aumento de tráfego estourou o limite de 100 requisições por minuto do PagaFácil (HTTP 429).",
    ),
    Cenario(
        id="banco_lento_com_deploy", titulo="Banco lento com deploy de distração", servico="pedidos-api",
        categoria="banco_de_dados", duracao=25, efeito=_banco_lento_com_deploy,
        causa_raiz="Uma reindexação no db-principal travou a tabela estoque. O deploy v3.2.1 do pedidos-api ocorreu na mesma hora, mas não é a causa.",
        deploy=Deploy("pedidos-api", "3.2.1", "e90a4d7", "joao.pereira", "Corrige texto do e-mail de confirmação", minutos_antes=2),
    ),
]}
