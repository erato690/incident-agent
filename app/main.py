"""Interface web própria: FastAPI serve o front estático (app/static) e a API do chat.

A API chama o mesmo agente integrado (`agente/integrado.py`), uma sessão por incidente. Os passos
do turno ("mascarando", "entendendo", "investigando", "auditando") chegam por SSE a partir dos
callbacks do LangChain: um handler entra em todas as execuções do turno por
`register_configure_hook`,
sem mudar o agente. Rodar: `uvicorn app.main:app --host 127.0.0.1 --port 8501`."""

import asyncio
import json
import os
import threading
import time
from collections.abc import Callable
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tracers.context import register_configure_hook
from pydantic import BaseModel, Field, field_validator

from agente.conversa import abrir_sessao as abrir_sessao_local
from agente.rastreamento import desligar_rastreamento_por_padrao
from agente.schemas import RespostaTurno, Sessao
from app.formatacao import (
    causa_a_confirmar,
    cenarios_disponiveis,
    dados_faltantes,
    fontes_consultadas,
    lacunas,
    markdown_resposta,
    mensagem_erro,
    perguntas,
    rotulo_ferramenta,
    tecnicas,
)

desligar_rastreamento_por_padrao()  # o app nunca rastreia no LangSmith
RAIZ = Path(__file__).resolve().parent.parent
PASTA_ESTATICA = Path(__file__).resolve().parent / "static"
PASTA_CENARIOS = RAIZ / "dados_dummy" / "cenarios"
PEDIDO_POSTMORTEM = "Gera o post-mortem deste incidente."
TEXTO_SEM_CHAVE = (
    "Chave de API não encontrada. Configure OPENAI_API_KEY (no .env local ou nas variáveis de "
    "ambiente do servidor) e reinicie o app."
)

# --- Passos do turno por callback (peça do LangChain, sem mudar o agente) ---

# Nome da execução no pipeline -> (etapa, texto mostrado ao engenheiro)
ETAPAS = {
    "passo1_mascara": ("mascarando", "Mascarando dados sensíveis"),
    "passo3_moderacao": ("moderando", "Checando a moderação"),
    "passo4_nlu": ("entendendo", "Entendendo a pergunta"),
    "auditoria": ("auditando", "Auditando a resposta"),
}
_progresso: ContextVar[BaseCallbackHandler | None] = ContextVar("progresso_turno", default=None)
register_configure_hook(_progresso, inheritable=True)


class Progresso(BaseCallbackHandler):
    """Converte o início das etapas e das ferramentas em eventos para o front."""

    def __init__(self, emitir: Callable[[dict], None]):
        self._emitir = emitir
        self._vistas: set[str] = set()

    def _uma_vez(self, etapa: str, texto: str) -> None:
        if etapa not in self._vistas:
            self._vistas.add(etapa)
            self._emitir({"etapa": etapa, "texto": texto})

    def on_chain_start(self, serialized, inputs, *, name: str | None = None, **kwargs) -> None:
        if name in ETAPAS:
            self._uma_vez(*ETAPAS[name])

    def on_tool_start(self, serialized, input_str, *, name: str | None = None, **kwargs) -> None:
        ferramenta = name or (serialized or {}).get("name") or "ferramenta"
        self._uma_vez("investigando", "Investigando")
        self._emitir(
            {"etapa": "consultando", "texto": f"Consultando {rotulo_ferramenta(ferramenta)}"}
        )


# --- Modelos da API ---


class NovaSessao(BaseModel):
    cenario: str


class NovaMensagem(BaseModel):
    texto: str = Field(max_length=8000)

    @field_validator("texto")
    @classmethod
    def _nao_vazio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("a mensagem está vazia")
        return valor.strip()


class Conversa:
    """Uma sessão do chat (um incidente) e as mensagens trocadas."""

    def __init__(self, sessao: Sessao, cenario: dict):
        self.sessao, self.cenario = sessao, cenario
        self.titulo: str | None = None
        self.mensagens: list[dict] = []
        self.trava = threading.Lock()

    def resumo(self) -> dict:
        return {
            "id": self.sessao.session_id,
            "cenario": self.cenario["id"],
            "titulo_cenario": self.cenario["titulo"],
            "servico": self.cenario.get("servico"),
            "titulo": self.titulo or self.cenario["titulo"],
            "criada_em": self.sessao.criada_em.isoformat(),
            "turnos": sum(1 for m in self.mensagens if m["papel"] == "agente"),
        }

    def completa(self) -> dict:
        return {**self.resumo(), "mensagens": self.mensagens}


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _mensagem_agente(resposta: RespostaTurno | None, duracao_ms: int, erro: str | None) -> dict:
    base = {"id": str(uuid4()), "papel": "agente", "criada_em": _agora(), "duracao_ms": duracao_ms}
    if resposta is None:
        return {**base, "resposta": None, "erro": erro, "texto": erro or "", "fontes": []}
    return {
        **base,
        "resposta": resposta.model_dump(mode="json"),
        "erro": None,
        "texto": markdown_resposta(resposta),
        "fontes": fontes_consultadas(resposta),
        "dados_faltantes": dados_faltantes(resposta),
        "perguntas": perguntas(resposta),
        "lacunas": lacunas(resposta),
        "investigado": fontes_consultadas(resposta),
        "causa_a_confirmar": causa_a_confirmar(resposta),
        "tecnicas": tecnicas(resposta),
    }


def _chave_no_ambiente() -> bool:
    from dotenv import load_dotenv

    load_dotenv()
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY"))


def _agente_padrao() -> Callable[[], Any]:
    """Monta o agente integrado na primeira mensagem (o import do app não exige chave)."""
    trava, guardado = threading.Lock(), {}

    def obter():
        with trava:
            if "agente" not in guardado:
                from agente.config import escolher_llm
                from agente.integrado import montar_agente_integrado

                guardado["agente"] = montar_agente_integrado(escolher_llm())
            return guardado["agente"]

    return obter


def criar_app(
    obter_agente: Callable[[], Any] | None = None,
    chave_configurada: Callable[[], bool] = _chave_no_ambiente,
) -> FastAPI:
    obter_agente = obter_agente or _agente_padrao()
    cenarios = {c["id"]: c for c in cenarios_disponiveis(PASTA_CENARIOS)}
    conversas: dict[str, Conversa] = {}
    app = FastAPI(title="Agente de incidentes", docs_url="/api/docs", redoc_url=None)

    @app.middleware("http")
    async def sem_cache_no_front(pedido, chamar):
        """O front muda junto com o agente: sem cache, o navegador nunca roda um app.js antigo."""
        resposta = await chamar(pedido)
        if not pedido.url.path.startswith("/api/"):
            resposta.headers["Cache-Control"] = "no-cache"
        return resposta

    def _conversa(session_id: str) -> Conversa:
        if session_id not in conversas:
            raise HTTPException(404, "Sessão não encontrada.")
        return conversas[session_id]

    def _exigir_chave() -> None:
        if not chave_configurada():
            raise HTTPException(503, TEXTO_SEM_CHAVE)

    def _turno(conversa: Conversa, texto: str, emitir: Callable[[dict], None] | None) -> dict:
        """Roda um turno do agente (bloqueante) e guarda as duas mensagens na sessão."""
        with conversa.trava:
            conversa.mensagens.append(
                {"id": str(uuid4()), "papel": "engenheiro", "texto": texto, "criada_em": _agora()}
            )
            if conversa.titulo is None and texto != PEDIDO_POSTMORTEM:
                conversa.titulo = texto[:60]
            token = _progresso.set(Progresso(emitir)) if emitir else None
            inicio = time.perf_counter()
            try:
                resposta, erro = obter_agente().turno(conversa.sessao, texto), None
            except Exception as excecao:  # falha inesperada: texto legível, sem pilha
                resposta, erro = None, mensagem_erro(excecao)
            finally:
                if token is not None:
                    _progresso.reset(token)
            mensagem = _mensagem_agente(resposta, int((time.perf_counter() - inicio) * 1000), erro)
            conversa.mensagens.append(mensagem)
            return mensagem

    @app.get("/", include_in_schema=False)
    def pagina():
        return FileResponse(PASTA_ESTATICA / "index.html")

    @app.get("/api/estado")
    def estado():
        padrao = os.getenv("CENARIO")
        return {
            "chave_configurada": chave_configurada(),
            "cenario_padrao": padrao if padrao in cenarios else None,
        }

    @app.get("/api/cenarios")
    def listar_cenarios():
        return list(cenarios.values())

    @app.get("/api/sessoes")
    def listar_sessoes():
        return [
            c.resumo()
            for c in sorted(conversas.values(), key=lambda c: c.sessao.criada_em, reverse=True)
        ]

    @app.post("/api/sessoes", status_code=201)
    def criar_sessao(pedido: NovaSessao):
        if pedido.cenario not in cenarios:
            raise HTTPException(422, f"Cenário desconhecido: {pedido.cenario}")
        if chave_configurada():
            sessao = obter_agente().abrir_sessao(pedido.cenario)
        else:
            sessao = abrir_sessao_local(pedido.cenario)
        conversa = Conversa(sessao, cenarios[pedido.cenario])
        conversas[sessao.session_id] = conversa
        return conversa.completa()

    @app.get("/api/sessoes/{session_id}")
    def abrir_sessao(session_id: str):
        return _conversa(session_id).completa()

    @app.post("/api/sessoes/{session_id}/mensagens")
    def enviar(session_id: str, pedido: NovaMensagem):
        conversa = _conversa(session_id)
        _exigir_chave()
        return _turno(conversa, pedido.texto, None)

    @app.post("/api/sessoes/{session_id}/mensagens/stream")
    async def enviar_com_passos(session_id: str, pedido: NovaMensagem):
        conversa = _conversa(session_id)
        _exigir_chave()
        fila: asyncio.Queue = asyncio.Queue()
        laco = asyncio.get_running_loop()

        def emitir(evento: dict) -> None:
            laco.call_soon_threadsafe(fila.put_nowait, ("passo", evento))

        async def trabalhar():
            mensagem = await asyncio.to_thread(_turno, conversa, pedido.texto, emitir)
            await fila.put(("erro" if mensagem["erro"] else "resposta", mensagem))

        async def eventos():
            tarefa = asyncio.create_task(trabalhar())
            while True:
                nome, dados = await fila.get()
                yield f"event: {nome}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"
                if nome != "passo":
                    break
            await tarefa

        cabecalhos = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        return StreamingResponse(eventos(), media_type="text/event-stream", headers=cabecalhos)

    @app.post("/api/sessoes/{session_id}/postmortem")
    def postmortem(session_id: str):
        conversa = _conversa(session_id)
        _exigir_chave()
        return _turno(conversa, PEDIDO_POSTMORTEM, None)

    @app.get("/api/sessoes/{session_id}/analise")
    def analise(session_id: str):
        _conversa(session_id)
        if not chave_configurada():
            return []
        turnos = obter_agente().registro.listar(session_id)
        return [t.model_dump(mode="json") for t in turnos]

    app.mount("/static", StaticFiles(directory=PASTA_ESTATICA), name="static")
    return app


app = criar_app()
