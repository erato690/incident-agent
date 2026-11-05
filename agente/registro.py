"""Registro dos turnos do agente integrado (base da aba de análise e da avaliação)."""

import json
import threading
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from agente.mascara import mascarar
from agente.schemas import PassoTrajetoria, RespostaTurno


def _agora() -> datetime:
    return datetime.now().astimezone()


def _texto_resposta(resposta: RespostaTurno) -> str:
    if resposta.analise is not None:
        principal = max(resposta.analise.hipoteses, key=lambda h: h.confianca)
        return f"{resposta.analise.resumo} Hipótese principal: {principal.causa}"
    if resposta.fixa is not None:
        return resposta.fixa.texto
    return resposta.erro or ""


class RegistroTurno(BaseModel):
    session_id: str
    incidente_id: str | None = None
    cenario: str | None = None
    pergunta: str
    rota: str
    resposta: str
    intencao: str | None = None
    ferramentas: list[str] = Field(default_factory=list)
    trajetoria: list[PassoTrajetoria] = Field(default_factory=list)
    auditoria_aprovada: bool | None = None
    motivos_auditoria: list[str] = Field(default_factory=list)
    aviso: str | None = None
    duracao_ms: int = Field(ge=0)
    criado_em: datetime = Field(default_factory=_agora)

    @classmethod
    def de_resposta(
        cls,
        session_id: str,
        pergunta: str,
        resposta: RespostaTurno,
        duracao_ms: int,
        incidente_id: str | None = None,
        cenario: str | None = None,
    ) -> "RegistroTurno":
        auditoria = getattr(resposta, "auditoria", None)
        nlu = resposta.nlu
        return cls(
            session_id=session_id,
            incidente_id=incidente_id,
            cenario=cenario,
            pergunta=mascarar(pergunta),
            rota=resposta.rota,
            resposta=_texto_resposta(resposta),
            intencao=nlu.intencao if nlu else (resposta.fixa.categoria if resposta.fixa else None),
            ferramentas=[p.ferramenta for p in resposta.trajetoria],
            trajetoria=list(resposta.trajetoria),
            auditoria_aprovada=getattr(auditoria, "aprovada", None),
            motivos_auditoria=list(getattr(auditoria, "motivos", None) or []),
            aviso=getattr(resposta, "aviso", None),
            duracao_ms=duracao_ms,
        )


class Registro:
    """Lista de turnos em memória, com persistência em JSON."""

    def __init__(self, turnos: list[RegistroTurno] | None = None) -> None:
        self._turnos = list(turnos or [])
        self._trava = threading.Lock()

    def adicionar(self, turno: RegistroTurno) -> None:
        with self._trava:
            self._turnos.append(turno)

    def listar(self, session_id: str | None = None) -> list[RegistroTurno]:
        with self._trava:
            return [t for t in self._turnos if session_id is None or t.session_id == session_id]

    def salvar(self, arquivo: Path) -> None:
        arquivo = Path(arquivo)
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        dados = [t.model_dump(mode="json") for t in self.listar()]
        arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def carregar(cls, arquivo: Path) -> "Registro":
        arquivo = Path(arquivo)
        if not arquivo.exists():
            return cls()
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        return cls([RegistroTurno.model_validate(d) for d in dados])
