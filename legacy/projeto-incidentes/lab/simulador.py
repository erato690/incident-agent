"""Gera o tráfego do sistema simulado e injeta falhas no CloudWatch (moto ou AWS).

Cada tick representa um minuto do sistema: todos os serviços escrevem logs e métricas,
os incidentes ativos alteram esses sinais e o detector publica alarmes.
"""

import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import Random

from botocore.exceptions import ClientError

from .aws import cliente
from .cenarios import CENARIOS, Cenario
from .sistema import (
    GRUPO_ALARMES, GRUPO_DEPLOYS, LIMITES, METRICAS, NAMESPACE, POOL_MAX, SERVICOS, grupo_logs,
)

DADOS = Path(__file__).resolve().parent.parent / "dados"
GABARITO = DADOS / "gabarito.jsonl"
FILA_INJECAO = DADOS / "injetar.txt"
STREAM = "principal"

UNIDADES = {
    "Requisicoes": "Count", "Erros5xx": "Count", "LatenciaP95": "Milliseconds",
    "MemoriaPct": "Percent", "ConexoesDB": "Count",
}


@dataclass
class Incidente:
    id: str
    cenario: Cenario
    inicio_tick: int  # primeiro tick com sintomas
    inicio: datetime | None = None

    def ativo(self, tick: int) -> bool:
        return self.inicio_tick <= tick < self.inicio_tick + self.cenario.duracao


def preparar_grupos() -> None:
    logs = cliente("logs")
    grupos = [grupo_logs(s) for s in SERVICOS] + [GRUPO_DEPLOYS, GRUPO_ALARMES]
    for grupo in grupos:
        for chamada, kwargs in (
            (logs.create_log_group, {"logGroupName": grupo}),
            (logs.create_log_stream, {"logGroupName": grupo, "logStreamName": STREAM}),
        ):
            try:
                chamada(**kwargs)
            except ClientError as erro:
                if erro.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                    raise


class Simulador:
    def __init__(self, seed: int | None = None):
        self.rng = Random(seed)
        self.logs = cliente("logs")
        self.cw = cliente("cloudwatch")
        self.versoes = {s: c["versao"] for s, c in SERVICOS.items()}
        self.incidentes: list[Incidente] = []
        self.alarmes_ativos: set[tuple[str, str]] = set()
        self.tick = 0

    # ---------- incidentes ----------

    def agendar(self, cenario_id: str, ts: datetime, em_ticks: int = 0) -> Incidente:
        cenario = CENARIOS[cenario_id]
        atraso = cenario.deploy.minutos_antes if cenario.deploy else 0
        incidente = Incidente(
            id=f"INC-{uuid.UUID(int=self.rng.getrandbits(128)).hex[:6].upper()}",
            cenario=cenario,
            inicio_tick=self.tick + em_ticks + atraso,
        )
        self.incidentes.append(incidente)
        return incidente

    def _deploys_do_tick(self, ts: datetime) -> list[str]:
        eventos = []
        for inc in self.incidentes:
            d = inc.cenario.deploy
            if d and self.tick == inc.inicio_tick - d.minutos_antes:
                self.versoes[d.servico] = d.versao
                eventos.append(json.dumps({
                    "evento": "deploy", "servico": d.servico, "versao": d.versao,
                    "commit": d.commit, "autor": d.autor, "mudanca": d.mudanca,
                    "ambiente": "producao", "status": "concluido",
                }, ensure_ascii=False))
        return eventos

    def _registrar_gabarito(self, inc: Incidente, ts: datetime, intervalo: timedelta) -> None:
        DADOS.mkdir(exist_ok=True)
        c = inc.cenario
        fim = ts + intervalo * c.duracao
        with GABARITO.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "id": inc.id, "cenario": c.id, "titulo": c.titulo, "servico": c.servico,
                "categoria": c.categoria, "causa_raiz": c.causa_raiz,
                "inicio": ts.isoformat(), "fim": fim.isoformat(),
                "deploy": {"servico": c.deploy.servico, "versao": c.deploy.versao, "commit": c.deploy.commit} if c.deploy else None,
            }, ensure_ascii=False) + "\n")

    # ---------- sinais ----------

    def _metricas_base(self, servico: str) -> dict[str, float]:
        cfg = SERVICOS[servico]
        onda = 1 + 0.25 * math.sin(self.tick / 60 * math.pi)  # ciclo suave de tráfego
        req = cfg["req_base"] * onda * self.rng.uniform(0.9, 1.1)
        return {
            "Requisicoes": round(req),
            "Erros5xx": self.rng.choice([0, 0, 0, 1, 1, 2]),
            "LatenciaP95": round(cfg["latencia_base"] * self.rng.uniform(0.85, 1.2)),
            "MemoriaPct": round(self.rng.uniform(40, 55), 1),
            "ConexoesDB": min(POOL_MAX, round(req / 40 + self.rng.uniform(0, 2))) if cfg["usa_db"] else 0,
        }

    def _linha(self, servico: str, nivel: str, msg: str) -> str:
        return json.dumps({
            "nivel": nivel, "servico": servico, "versao": self.versoes[servico],
            "trace_id": f"{self.rng.getrandbits(64):016x}", "msg": msg,
        }, ensure_ascii=False)

    def _logs_normais(self, servico: str, metricas: dict[str, float]) -> list[str]:
        cfg = SERVICOS[servico]
        linhas = []
        for _ in range(self.rng.randint(3, 6)):
            rota = self.rng.choice(cfg["rotas"])
            lat = round(metricas["LatenciaP95"] * self.rng.uniform(0.3, 0.9))
            linhas.append(self._linha(servico, "INFO", f"{rota} 200 em {lat}ms"))
        return linhas

    def _detector(self, metricas: dict[str, dict[str, float]]) -> list[str]:
        eventos = []
        for servico, valores in metricas.items():
            checagens = [(m, valores[m], lim, valores[m] > lim) for m, lim in LIMITES.items()]
            checagens.append(("Requisicoes", valores["Requisicoes"], 0, valores["Requisicoes"] == 0))
            for metrica, valor, limite, violado in checagens:
                chave = (servico, metrica)
                if violado and chave not in self.alarmes_ativos:
                    self.alarmes_ativos.add(chave)
                    estado = "ALARME"
                elif not violado and chave in self.alarmes_ativos:
                    self.alarmes_ativos.discard(chave)
                    estado = "OK"
                else:
                    continue
                eventos.append(json.dumps({
                    "estado": estado, "alarme": f"{servico}-{metrica}", "servico": servico,
                    "metrica": metrica, "valor": valor, "limite": limite,
                }, ensure_ascii=False))
        return eventos

    # ---------- um minuto do sistema ----------

    def passo(self, ts: datetime, intervalo: timedelta = timedelta(minutes=1)) -> list[Incidente]:
        """Gera e envia um tick. Devolve os incidentes que começaram neste tick."""
        ms = int(ts.timestamp() * 1000)
        deploys = self._deploys_do_tick(ts)
        metricas = {s: self._metricas_base(s) for s in SERVICOS}
        linhas = {s: self._logs_normais(s, metricas[s]) for s in SERVICOS}

        iniciados = []
        for inc in self.incidentes:
            if not inc.ativo(self.tick):
                continue
            t = self.tick - inc.inicio_tick
            if t == 0:
                inc.inicio = ts
                self._registrar_gabarito(inc, ts, intervalo)
                iniciados.append(inc)
            efeito = inc.cenario.efeito(t, inc.cenario.duracao, self.rng)
            for (servico, metrica), valor in efeito.metricas.items():
                metricas[servico][metrica] = valor
            for servico, nivel, msg in efeito.logs:
                linhas[servico].append(self._linha(servico, nivel, msg))

        for servico in SERVICOS:
            if metricas[servico]["Requisicoes"] == 0:
                linhas[servico] = [l for l in linhas[servico] if '"INFO"' not in l or "reiniciado" in l]
        alarmes = self._detector(metricas)

        for servico, msgs in linhas.items():
            self._enviar_logs(grupo_logs(servico), msgs, ms)
        self._enviar_logs(GRUPO_DEPLOYS, deploys, ms)
        self._enviar_logs(GRUPO_ALARMES, alarmes, ms)
        self._enviar_metricas(metricas, ts)

        self.incidentes = [i for i in self.incidentes if self.tick < i.inicio_tick + i.cenario.duracao]
        self.tick += 1
        return iniciados

    def _enviar_logs(self, grupo: str, msgs: list[str], ms: int) -> None:
        if not msgs:
            return
        eventos = [{"timestamp": ms + i, "message": m} for i, m in enumerate(msgs)]
        self.logs.put_log_events(logGroupName=grupo, logStreamName=STREAM, logEvents=eventos)

    def _enviar_metricas(self, metricas: dict[str, dict[str, float]], ts: datetime) -> None:
        dados = [
            {
                "MetricName": m, "Dimensions": [{"Name": "Servico", "Value": s}],
                "Timestamp": ts, "Value": float(v), "Unit": UNIDADES[m],
            }
            for s, valores in metricas.items() for m, v in valores.items() if m in METRICAS
        ]
        self.cw.put_metric_data(Namespace=NAMESPACE, MetricData=dados)


def agora() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)
