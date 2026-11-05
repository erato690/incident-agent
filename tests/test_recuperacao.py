"""Recuperação sobre FAISS: corpus real, embeddings falsos, índice em pasta temporária."""

from pathlib import Path

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.messages import ToolMessage

from agente import recuperacao
from agente.ferramentas import PREFIXO
from agente.recuperacao import (
    buscar_com_score,
    carregar_documentos,
    carregar_indice,
    construir_indice,
    dividir,
    ferramenta_retriever_comparacao,
    montar_agente_recuperacao,
    montar_ferramenta_recuperacao,
)
from tests.fakes import chamada, roteiro

PASTA = Path(__file__).resolve().parent.parent / "dados" / "documentos"


@pytest.fixture
def embeddings():
    return DeterministicFakeEmbedding(size=64)


@pytest.fixture
def indice(embeddings, tmp_path):
    construir_indice(embeddings, tmp_path / "indice", PASTA)
    return carregar_indice(tmp_path / "indice", embeddings)


def test_carrega_os_dez_documentos_com_metadados():
    docs = carregar_documentos(PASTA)
    assert len(docs) == 10
    assert {d.metadata["tipo"] for d in docs} == {"runbook", "documentacao"}
    assert sum(d.metadata["tipo"] == "runbook" for d in docs) == 8
    for d in docs:
        assert d.metadata["titulo"] and d.metadata["servico"] and d.metadata["assunto"]
        assert d.metadata["arquivo"].endswith(".md")
        assert "---" not in d.page_content.splitlines()[0]


def test_cabecalho_nao_entra_no_texto():
    docs = carregar_documentos(PASTA)
    assert all("tipo:" not in d.page_content for d in docs)


def test_runbook_de_pool_nao_usa_palavras_da_pergunta_crua():
    pool = next(d for d in carregar_documentos(PASTA) if "pool" in d.metadata["arquivo"])
    texto = pool.page_content.lower()
    assert not any(p in texto for p in ("travando", "travado", "site", "lento"))


def test_dividir_preserva_metadados():
    pedacos = dividir(carregar_documentos(PASTA))
    assert len(pedacos) >= 10
    assert all("titulo" in p.metadata for p in pedacos)


def test_ida_e_volta_do_indice(embeddings, tmp_path):
    construir_indice(embeddings, tmp_path / "i", PASTA)
    assert (tmp_path / "i" / "index.faiss").exists()
    carregado = carregar_indice(tmp_path / "i", embeddings)
    resultados = buscar_com_score(carregado, "pool de conexões", k=3)
    assert len(resultados) == 3
    assert all(isinstance(score, float) for _, score in resultados)


def test_indice_ausente_da_erro_claro(embeddings, tmp_path):
    with pytest.raises(FileNotFoundError, match="scripts/construir_indice.py"):
        carregar_indice(tmp_path / "nao_existe", embeddings)


def test_filtro_por_tipo(indice):
    resultados = buscar_com_score(indice, "limite", k=5, filtro={"tipo": "documentacao"})
    assert resultados
    assert {doc.metadata["tipo"] for doc, _ in resultados} == {"documentacao"}


def test_ferramenta_devolve_titulo_tipo_e_score(indice):
    ferramenta = montar_ferramenta_recuperacao(indice, limiar=1e6)
    saida = ferramenta.invoke({"consulta": "limite de requisições"})
    assert saida.startswith(PREFIXO)
    assert "tipo:" in saida and "score" in saida.lower()
    assert "sem cobertura" not in saida.lower()


def test_ferramenta_declara_sem_cobertura_com_limiar_baixo(indice):
    ferramenta = montar_ferramenta_recuperacao(indice, limiar=0.0)
    saida = ferramenta.invoke({"consulta": "qualquer coisa"})
    assert "sem cobertura" in saida.lower()


def test_ferramenta_filtra_por_tipo(indice):
    ferramenta = montar_ferramenta_recuperacao(indice, limiar=1e6)
    saida = ferramenta.invoke({"consulta": "limite", "tipo": "documentacao"})
    assert "tipo: runbook" not in saida


def test_limiar_padrao_e_o_da_aula():
    assert recuperacao.LIMIAR_SEM_COBERTURA == 1.15


def test_agente_chama_buscar_documentacao(indice):
    modelo = roteiro(
        chamada("buscar_documentacao", {"consulta": "connection pool exhausted"}),
        "Sem cobertura suficiente.",
    )
    agente = montar_agente_recuperacao(modelo, indice)
    resultado = agente.invoke({"messages": [("user", "o site está travando")]})
    observacoes = [m for m in resultado["messages"] if isinstance(m, ToolMessage)]
    assert len(observacoes) == 1 and observacoes[0].name == "buscar_documentacao"
    assert resultado["messages"][-1].content == "Sem cobertura suficiente."


def test_prompt_do_agente_termina_em_portugues():
    assert recuperacao.SISTEMA_RECUPERACAO.endswith("Always answer in Brazilian Portuguese.")
    assert "query transformation" in recuperacao.SISTEMA_RECUPERACAO


def test_retriever_de_comparacao(indice):
    ferramenta = ferramenta_retriever_comparacao(indice)
    assert ferramenta.name == "buscar_documentacao_retriever"
    assert "pool" in ferramenta.invoke({"query": "pool de conexões esgotado"}).lower()
