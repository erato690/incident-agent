"""Memória de longo prazo: episódica (incidentes) e semântica (fatos).

Um único `InMemoryVectorStore` guarda `Document`s; o campo `tipo` do metadata
separa os dois espaços e toda busca filtra por ele. A persistência é um JSON sem vetores.
"""

import hashlib
import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import Runnable
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

from agente.mascara import mascarar
from agente.schemas import (
    Episodio,
    EpisodioEncontrado,
    FatoSemantico,
    FatoSemanticoEncontrado,
    ResolucaoMemoria,
    ResultadoRegistro,
)

__all__ = ["SIMILARIDADE_MINIMA", "MemoriaLongoPrazo", "embeddings_padrao"]

LIMITE_BUSCA = 50
CANDIDATOS = 3
PESO_SIMILARIDADE, PESO_RECENCIA = 0.7, 0.2
BONUS_POR_ACESSO, TETO_BONUS = 0.01, 0.15
DECAIMENTO_POR_DIA = 0.05
# Calibração D8 (specs/003-fase3-memoria/research.md), consulta com a linha de log principal:
# mesmo incidente 0,61; outros cenários <= 0,49.
SIMILARIDADE_MINIMA = 0.55
SEM_CANDIDATOS = "Nenhum episódio ativo parecido no serviço; é um incidente novo."

logger = logging.getLogger(__name__)


def embeddings_padrao() -> Embeddings:
    """Embeddings da OpenAI (o padrão da biblioteca é o ada-002, por isso o modelo explícito)."""
    return OpenAIEmbeddings(model="text-embedding-3-small")


def _texto_indexado(episodio: Episodio) -> str:
    """Único texto que entra no embedding: resumo + serviço + causa + evidência."""
    partes = [episodio.resumo, episodio.servico, episodio.causa, episodio.evidencia]
    return " ".join(parte for parte in partes if parte)


def _mascarar_episodio(episodio: Episodio) -> Episodio:
    return episodio.model_copy(
        update={
            "resumo": mascarar(episodio.resumo),
            "causa": mascarar(episodio.causa),
            "evidencia": mascarar(episodio.evidencia) if episodio.evidencia else None,
        }
    )


def _similaridade(score: float | None) -> float:
    return min(1.0, max(0.0, score or 0.0))


def _descrever(episodio: Episodio) -> str:
    return (
        f"ID: {episodio.id_memoria} | Incidente: {episodio.incidente_id} | "
        f"Resumo: {episodio.resumo} | Causa: {episodio.causa}"
    )


def _pontuacao(similaridade: float, dias: int, acessos: int) -> float:
    recencia = 1.0 / (1.0 + DECAIMENTO_POR_DIA * dias)
    bonus = min(TETO_BONUS, acessos * BONUS_POR_ACESSO)
    return PESO_SIMILARIDADE * similaridade + PESO_RECENCIA * recencia + bonus


class MemoriaLongoPrazo:
    """Dois espaços no mesmo store, separados pelo metadata `tipo`: "episodica" e "semantica"."""

    def __init__(
        self,
        embeddings: Embeddings,
        arquivo: Path | None = None,
        agora: Callable[[], datetime] = datetime.now,
    ):
        self._embeddings = embeddings
        self._store = InMemoryVectorStore(embedding=embeddings)
        self._arquivo = arquivo
        self.agora = agora

    # --- documentos ------------------------------------------------------------------------

    @staticmethod
    def _documento_episodio(episodio: Episodio) -> Document:
        return Document(
            id=episodio.id_memoria,
            page_content=_texto_indexado(episodio),
            metadata={"tipo": "episodica", **episodio.model_dump(mode="json")},
        )

    @staticmethod
    def _episodio_do_documento(documento: Document) -> Episodio:
        return Episodio.model_validate(
            {chave: valor for chave, valor in documento.metadata.items() if chave != "tipo"}
        )

    def _gravar_episodio(self, episodio: Episodio) -> None:
        self._gravar_episodios([episodio])

    def _gravar_episodios(self, episodios: list[Episodio]) -> None:
        documentos = [self._documento_episodio(episodio) for episodio in episodios]
        if documentos:
            self._store.add_documents(documentos, ids=[d.id for d in documentos])

    def _atualizar_metadados(self, id_memoria: str, **campos) -> None:
        """Muda o metadata de um documento já guardado, sem reembedar (não gasta chamada de API).
        Os `Document`s devolvidos pelo store são cópias (o pydantic copia o dict), então a
        mudança vai direto no registro interno (`store.store`), onde o vetor fica intocado."""
        registro = self._store.store.get(id_memoria)
        if registro is not None:
            registro["metadata"].update(campos)

    def _documentos_episodicos(self, servico: str | None = None) -> list[Document]:
        """Documentos episódicos do serviço (de todos, sem `servico`), sem busca (não reembeda,
        não conta acesso)."""
        return [
            Document(id=d["id"], page_content=d["text"], metadata=d["metadata"])
            for d in self._store.store.values()
            if d["metadata"]["tipo"] == "episodica"
            and (servico is None or d["metadata"]["servico"] == servico)
        ]

    # --- episódica -------------------------------------------------------------------------

    def obter_episodio(self, servico: str, id_memoria: str) -> Episodio | None:
        for documento in self._store.get_by_ids([id_memoria]):
            meta = documento.metadata
            if meta["tipo"] == "episodica" and meta["servico"] == servico:
                return self._episodio_do_documento(documento)
        return None

    def _buscar_ativos(self, servico: str, texto: str, k: int) -> list[tuple[Document, float]]:
        """Busca por similaridade (cosseno) só nos episódios ativos do serviço."""
        return self._store.similarity_search_with_score(
            texto,
            k=k,
            filter=lambda d: (
                d.metadata["tipo"] == "episodica"
                and d.metadata["servico"] == servico
                and d.metadata["status"] == "ativo"
            ),
        )

    def _candidatos(self, episodio: Episodio) -> list[Episodio]:
        """Episódios ativos parecidos do mesmo serviço (a busca do 'apêndice do cérebro')."""
        achados = self._buscar_ativos(episodio.servico, _texto_indexado(episodio), CANDIDATOS)
        return [self._episodio_do_documento(documento) for documento, _ in achados]

    def _resolver(self, episodio: Episodio, resolver: Runnable) -> ResolucaoMemoria:
        candidatos = self._candidatos(episodio)
        if not candidatos:
            return ResolucaoMemoria(acao="inserir_novo", motivo=SEM_CANDIDATOS)
        decisao = resolver.invoke(
            {
                "existentes": "\n".join(_descrever(c) for c in candidatos),
                "novo": f"Incidente: {episodio.incidente_id} | Resumo: {episodio.resumo} | "
                f"Causa: {episodio.causa}",
            }
        )
        return self._validar_decisao(decisao, episodio)

    def _validar_decisao(self, decisao: ResolucaoMemoria, novo: Episodio) -> ResolucaoMemoria:
        """Trava: só se atualiza um episódio ativo do mesmo incidente; o resto vira inserção."""
        if decisao.acao == "inserir_novo":
            return decisao
        antigo = self.obter_episodio(novo.servico, decisao.id_memoria_antiga or "")
        if antigo is None or antigo.status != "ativo":
            correcao = "id da memória antiga inexistente ou já arquivado; gravado como novo"
        elif antigo.incidente_id != novo.incidente_id:
            correcao = (
                f"o episódio {antigo.id_memoria} é de outro incidente "
                f"({antigo.incidente_id}); gravado como novo"
            )
        else:
            return decisao
        logger.warning("Atualização recusada: %s", correcao)
        return ResolucaoMemoria(
            acao="inserir_novo", motivo=f"{decisao.motivo} [correção: {correcao}]"
        )

    def registrar_episodio(self, episodio: Episodio, resolver: Runnable) -> ResultadoRegistro:
        """Resolução de memória: insere o episódio novo ou arquiva o antigo e grava o novo."""
        decisao = self._resolver(_mascarar_episodio(episodio), resolver)
        novo = _mascarar_episodio(episodio).model_copy(
            update={"status": "ativo", "motivo_registro": decisao.motivo, "acessos": 0}
        )
        arquivado = None
        if decisao.acao == "atualizar_existente":
            antigo = self.obter_episodio(novo.servico, decisao.id_memoria_antiga)
            arquivado = antigo.model_copy(update={"status": "arquivado"})
            novo = novo.model_copy(update={"substitui": antigo.id_memoria})
            self._atualizar_metadados(antigo.id_memoria, status="arquivado")
        self._gravar_episodios([novo])
        self.salvar()
        return ResultadoRegistro(decisao=decisao, episodio=novo, arquivado=arquivado)

    def consultar_episodios(
        self,
        servico: str,
        texto: str,
        k: int = 3,
        similaridade_minima: float = SIMILARIDADE_MINIMA,
    ) -> list[EpisodioEncontrado]:
        """Ativos do serviço por relevância (similaridade, recência e acessos); soma um acesso.
        Quem tem similaridade abaixo do limiar é descartado antes de ordenar e de contar acesso."""
        resultados = self._buscar_ativos(servico, texto, LIMITE_BUSCA)
        achados = [self._encontrado(documento, score) for documento, score in resultados]
        achados = [a for a in achados if a.similaridade >= similaridade_minima]
        achados.sort(key=lambda achado: achado.pontuacao, reverse=True)
        devolvidos = achados[:k]
        for achado in devolvidos:
            self._atualizar_metadados(achado.episodio.id_memoria, acessos=achado.acessos + 1)
        return devolvidos

    def _encontrado(self, documento: Document, score: float) -> EpisodioEncontrado:
        episodio = self._episodio_do_documento(documento)
        dias = max(0, (self.agora() - episodio.criado_em).days)
        similaridade = _similaridade(score)
        return EpisodioEncontrado(
            episodio=episodio,
            similaridade=similaridade,
            dias=dias,
            acessos=episodio.acessos,
            pontuacao=_pontuacao(similaridade, dias, episodio.acessos),
        )

    def listar_episodios(self, servico: str, incluir_arquivados: bool = True) -> list[Episodio]:
        """Auditoria (antes x depois): do mais antigo ao mais novo, sem contar acesso."""
        episodios = [self._episodio_do_documento(d) for d in self._documentos_episodicos(servico)]
        if not incluir_arquivados:
            episodios = [e for e in episodios if e.status == "ativo"]
        return sorted(episodios, key=lambda episodio: episodio.criado_em)

    def episodios_da_sessao(self, session_id: str) -> list[Episodio]:
        """Episódios ativos gravados nesta sessão, de qualquer serviço (o serviço do turno de
        confirmação pode diferir do da investigação), do mais antigo ao mais novo."""
        achados = [self._episodio_do_documento(d) for d in self._documentos_episodicos()]
        dela = [e for e in achados if e.session_id == session_id and e.status == "ativo"]
        return sorted(dela, key=lambda episodio: episodio.criado_em)

    # --- semântica (só interface) ----------------------------------------------------------

    @staticmethod
    def _documento_fato(fato: FatoSemantico) -> Document:
        fato = fato.model_copy(update={"fato": mascarar(fato.fato)})
        return Document(
            id=hashlib.sha1(fato.fato.encode()).hexdigest(),
            page_content=fato.fato,
            metadata={"tipo": "semantica", **fato.model_dump(mode="json")},
        )

    def _gravar_fatos(self, fatos: list[FatoSemantico]) -> None:
        documentos = [self._documento_fato(fato) for fato in fatos]
        if documentos:
            self._store.add_documents(documentos, ids=[d.id for d in documentos])

    def registrar_fato_semantico(self, fato: FatoSemantico) -> None:
        self._gravar_fatos([fato])
        self.salvar()

    def consultar_fatos_semanticos(
        self, assunto: str, texto: str, k: int = 3
    ) -> list[FatoSemanticoEncontrado]:
        chave = assunto.strip().casefold()  # o assunto gravado fica como veio
        resultados = self._store.similarity_search_with_score(
            texto,
            k=k,
            filter=lambda d: (
                d.metadata["tipo"] == "semantica"
                and d.metadata["assunto"].strip().casefold() == chave
            ),
        )
        achados = []
        for documento, score in resultados:
            fato = FatoSemantico.model_validate(
                {chave: valor for chave, valor in documento.metadata.items() if chave != "tipo"}
            )
            vencido = fato.valido_ate is not None and fato.valido_ate < self.agora()
            achados.append(
                FatoSemanticoEncontrado(
                    **fato.model_dump(exclude={"assunto"}),
                    similaridade=_similaridade(score),
                    vencido=vencido,
                )
            )
        return achados

    # --- persistência ----------------------------------------------------------------------

    def salvar(self) -> None:
        """Grava os dois espaços em JSON (no-op sem arquivo); chamada após cada registro."""
        if self._arquivo is None:
            return
        dados: dict[str, list[dict]] = {"episodica": [], "semantica": []}
        for item in self._store.store.values():
            meta = dict(item["metadata"])
            dados[meta.pop("tipo")].append(meta)
        self._arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def carregar(
        cls, arquivo: Path, embeddings: Embeddings, agora: Callable[[], datetime] = datetime.now
    ) -> "MemoriaLongoPrazo":
        """Reinsere (e reembeda) o conteúdo do JSON; arquivo ausente dá memória vazia."""
        memoria = cls(embeddings, arquivo, agora)
        if not arquivo.exists():
            return memoria
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        memoria._gravar_episodios([Episodio.model_validate(e) for e in dados.get("episodica", [])])
        memoria._gravar_fatos([FatoSemantico.model_validate(f) for f in dados.get("semantica", [])])
        return memoria
