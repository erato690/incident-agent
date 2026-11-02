"""Callback que registra cada chamada de ferramenta do agente (trajetória)."""

import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from agente.github import MARCA_RESERVA, PREFIXO_MOTIVO
from agente.schemas import PassoTrajetoria


def _motivo(texto: str) -> str | None:
    for linha in texto.splitlines():
        if linha.startswith(PREFIXO_MOTIVO):
            return linha.removeprefix(PREFIXO_MOTIVO)
    return None


class TrajetoriaCallback(BaseCallbackHandler):
    """Acumula `PassoTrajetoria` na ordem em que as ferramentas terminam."""

    def __init__(self) -> None:
        self.passos: list[PassoTrajetoria] = []
        self._abertas: dict[UUID, tuple[str, dict, float]] = {}

    def on_tool_start(
        self,
        serialized: dict,
        input_str: str,
        *,
        run_id: UUID,
        inputs: dict | None = None,
        **kwargs: Any,
    ) -> None:
        nome = (serialized or {}).get("name") or kwargs.get("name") or "desconhecida"
        self._abertas[run_id] = (nome, dict(inputs or {}), time.perf_counter())

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        texto = str(getattr(output, "content", output))
        self._fechar(
            run_id, tamanho=len(texto), reserva=MARCA_RESERVA in texto, motivo=_motivo(texto)
        )

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._fechar(run_id, tamanho=0, erro=str(error))

    def _fechar(
        self,
        run_id: UUID,
        tamanho: int,
        reserva: bool = False,
        erro: str | None = None,
        motivo: str | None = None,
    ) -> None:
        nome, args, inicio = self._abertas.pop(run_id, ("desconhecida", {}, time.perf_counter()))
        self.passos.append(
            PassoTrajetoria(
                ferramenta=nome,
                argumentos=args,
                duracao_ms=int((time.perf_counter() - inicio) * 1000),
                tamanho=tamanho,
                erro=erro,
                reserva=reserva,
                motivo_reserva=motivo,
            )
        )
