"""Schemas e MemoriaLongoPrazo: memória episódica (com resolução) e semântica separadas."""

import json
import logging
import re
from datetime import datetime, timedelta
from uuid import UUID

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.runnables import RunnableLambda
from langchain_core.vectorstores import InMemoryVectorStore
from pydantic import ValidationError

from agente.memoria import MemoriaLongoPrazo, embeddings_padrao
from agente.schemas import (
    CausaConfirmada,
    Episodio,
    FatoSemantico,
    ResolucaoMemoria,
    RespostaFixa,
    RespostaTurno,
    ResultadoModeracao,
    Sessao,
)

AGORA = datetime(2026, 11, 2, 12, 0)
MODERACAO = ResultadoModeracao(status="ok")


def _episodio(causa="pool de conexões esgotado", incidente_id="inc-1", servico="pedidos-api", **kw):
    dados = {
        "criado_em": AGORA,
        "origem": "engenheiro",
        "session_id": "t-1",
        "resumo": "500 no checkout",
    }
    return Episodio(incidente_id=incidente_id, servico=servico, causa=causa, **{**dados, **kw})


def _memoria(arquivo=None, agora=lambda: AGORA):
    return MemoriaLongoPrazo(DeterministicFakeEmbedding(size=64), arquivo, agora)


def _resolver(acao="inserir_novo", antigo=None, motivo="porque sim"):
    """Resolvedor falso; `antigo` pode ser uma função que recebe o texto dos candidatos."""
    entradas = []

    def decide(entrada):
        entradas.append(entrada)
        id_antigo = antigo(entrada) if callable(antigo) else antigo
        return ResolucaoMemoria(acao=acao, id_memoria_antiga=id_antigo, motivo=motivo)

    resolvedor = RunnableLambda(decide)
    resolvedor.entradas = entradas
    return resolvedor


def _id_do_primeiro(entrada):
    return re.search(r"ID: (\S+)", entrada["existentes"]).group(1)


# --- schemas ---------------------------------------------------------------------------------


def test_episodio_novo_tem_id_status_e_acessos_padrao():
    episodio = _episodio()
    assert str(UUID(episodio.id_memoria, version=4)) == episodio.id_memoria
    assert (episodio.status, episodio.substitui, episodio.acessos) == ("ativo", None, 0)
    assert not hasattr(episodio, "historico_causas")
    assert _episodio().id_memoria != episodio.id_memoria
    with pytest.raises(ValidationError):
        _episodio(origem="outro")


def test_resolucao_memoria_so_aceita_as_duas_acoes():
    assert ResolucaoMemoria(acao="inserir_novo", motivo="x").id_memoria_antiga is None
    with pytest.raises(ValidationError):
        ResolucaoMemoria(acao="apagar", motivo="x")


def test_fato_semantico_fonte_e_validade_opcional():
    fato = FatoSemantico(assunto="github", fato="60/h", fonte="documentacao", verificado_em=AGORA)
    assert fato.valido_ate is None
    with pytest.raises(ValidationError):
        FatoSemantico(assunto="g", fato="f", fonte="boato", verificado_em=AGORA)


def test_sessao_e_causa_confirmada():
    sessao = Sessao(session_id="t", criada_em=AGORA)
    assert sessao.turnos == 0 and sessao.servico is None and sessao.cenario is None
    causa = CausaConfirmada(resumo="500", causa="deploy", levantada_pelo_agente=False)
    assert causa.evidencia is None and "servico" not in CausaConfirmada.model_fields


def test_resposta_turno_rota_memoria_com_episodios_e_resolucao():
    episodio = _episodio()
    resolucao = ResolucaoMemoria(acao="inserir_novo", motivo="novo")
    resposta = RespostaTurno(
        rota="memoria",
        moderacao=MODERACAO,
        fixa=RespostaFixa(texto="ok", camada=2, categoria="confirmar_causa"),
        episodio=episodio,
        episodio_anterior=None,
        resolucao=resolucao,
    )
    assert resposta.episodio == episodio and resposta.resolucao == resolucao


# --- memória episódica -----------------------------------------------------------------------


def test_inserir_novo_cria_episodio_ativo_e_o_texto_indexado_tem_os_quatro_campos():
    memoria = _memoria()
    resultado = memoria.registrar_episodio(
        _episodio(evidencia="HikariPool no log", resumo="500 no checkout"), _resolver()
    )
    assert resultado.decisao.acao == "inserir_novo" and resultado.arquivado is None
    assert (
        resultado.episodio.status == "ativo"
        and resultado.episodio.motivo_registro == resultado.decisao.motivo
    )
    documento = memoria._store.get_by_ids([resultado.episodio.id_memoria])[0]
    assert documento.page_content == (
        "500 no checkout pedidos-api pool de conexões esgotado HikariPool no log"
    )
    achados = memoria.consultar_episodios("pedidos-api", "pool de conexões esgotado")
    assert [a.episodio.id_memoria for a in achados] == [resultado.episodio.id_memoria]


def test_sem_candidatos_o_resolvedor_nem_e_chamado():
    resolvedor = _resolver()
    _memoria().registrar_episodio(_episodio(), resolvedor)
    assert resolvedor.entradas == []


def test_resolvedor_recebe_so_ativos_do_mesmo_servico_com_id_e_incidente():
    memoria = _memoria()
    memoria.registrar_episodio(_episodio(incidente_id="inc-a"), _resolver())
    memoria.registrar_episodio(_episodio(servico="outro-api", incidente_id="inc-b"), _resolver())
    resolvedor = _resolver()
    memoria.registrar_episodio(_episodio(incidente_id="inc-c"), resolvedor)
    existentes = resolvedor.entradas[0]["existentes"]
    assert "inc-a" in existentes and "inc-b" not in existentes
    assert "inc-c" in resolvedor.entradas[0]["novo"]


def test_atualizar_arquiva_o_antigo_e_cria_novo_com_substitui():
    memoria = _memoria()
    antigo = memoria.registrar_episodio(_episodio("deploy v3.2.0"), _resolver()).episodio
    resultado = memoria.registrar_episodio(
        _episodio("limite de memória", session_id="t-2"),
        _resolver("atualizar_existente", _id_do_primeiro, "causa corrigida"),
    )
    assert resultado.decisao.acao == "atualizar_existente"
    assert resultado.arquivado.id_memoria == antigo.id_memoria
    assert resultado.arquivado.status == "arquivado"
    assert resultado.episodio.substitui == antigo.id_memoria
    assert (
        resultado.episodio.status == "ativo"
        and resultado.episodio.motivo_registro == "causa corrigida"
    )
    guardado = memoria.obter_episodio("pedidos-api", antigo.id_memoria)
    assert guardado.status == "arquivado" and guardado.causa == "deploy v3.2.0"


def test_troca_de_causa_preserva_o_antigo_arquivado_e_a_busca_so_acha_o_ativo():
    memoria = _memoria()
    memoria.registrar_episodio(_episodio("deploy v3.2.0 reduziu o pool"), _resolver())
    memoria.registrar_episodio(
        _episodio("limite de memória do container"),
        _resolver("atualizar_existente", _id_do_primeiro),
    )
    achados = memoria.consultar_episodios("pedidos-api", "deploy v3.2.0 reduziu o pool", k=5)
    assert [a.episodio.causa for a in achados] == ["limite de memória do container"]
    todos = memoria.listar_episodios("pedidos-api")
    assert {e.status for e in todos} == {"ativo", "arquivado"} and len(todos) == 2
    assert [
        e.status for e in memoria.listar_episodios("pedidos-api", incluir_arquivados=False)
    ] == ["ativo"]


def test_trava_atualizar_episodio_de_outro_incidente_vira_insercao(caplog):
    memoria = _memoria()
    antigo = memoria.registrar_episodio(
        _episodio("pool", incidente_id="inc-1"), _resolver()
    ).episodio
    with caplog.at_level(logging.WARNING):
        resultado = memoria.registrar_episodio(
            _episodio("pool de novo", incidente_id="inc-2"),
            _resolver("atualizar_existente", antigo.id_memoria, "parece o mesmo"),
        )
    assert resultado.decisao.acao == "inserir_novo" and resultado.decisao.id_memoria_antiga is None
    assert "parece o mesmo" in resultado.decisao.motivo and "inc-1" in resultado.decisao.motivo
    assert resultado.arquivado is None and resultado.episodio.substitui is None
    assert memoria.obter_episodio("pedidos-api", antigo.id_memoria).status == "ativo"
    assert len(memoria.listar_episodios("pedidos-api")) == 2
    assert any(r.levelname == "WARNING" for r in caplog.records)


def test_id_inexistente_ou_ausente_vira_insercao_com_motivo_anotado():
    memoria = _memoria()
    memoria.registrar_episodio(_episodio(), _resolver())
    for antigo in ("nao-existe", None):
        resultado = memoria.registrar_episodio(
            _episodio("outra", incidente_id="inc-1"), _resolver("atualizar_existente", antigo, "m")
        )
        assert resultado.decisao.acao == "inserir_novo" and resultado.arquivado is None
        assert resultado.decisao.motivo.startswith("m")
        assert len(resultado.decisao.motivo) > 1


def test_nao_atualiza_um_episodio_ja_arquivado():
    memoria = _memoria()
    primeiro = memoria.registrar_episodio(_episodio("a"), _resolver()).episodio
    memoria.registrar_episodio(
        _episodio("b"), _resolver("atualizar_existente", primeiro.id_memoria)
    )
    resultado = memoria.registrar_episodio(
        _episodio("c"), _resolver("atualizar_existente", primeiro.id_memoria)
    )
    assert resultado.decisao.acao == "inserir_novo" and resultado.arquivado is None


def test_relevancia_usa_a_formula_do_material():
    relogio = [AGORA]
    memoria = _memoria(agora=lambda: relogio[0])
    memoria.registrar_episodio(_episodio("pool"), _resolver())
    relogio[0] = AGORA + timedelta(days=20)
    primeiro = memoria.consultar_episodios("pedidos-api", "pool")[0]
    assert (primeiro.dias, primeiro.acessos) == (20, 0)
    esperado = 0.7 * primeiro.similaridade + 0.2 * (1 / (1 + 0.05 * 20)) + 0.0
    assert primeiro.pontuacao == pytest.approx(esperado)
    segundo = memoria.consultar_episodios("pedidos-api", "pool")[0]
    assert segundo.acessos == 1
    assert segundo.pontuacao == pytest.approx(esperado + 0.01)


def test_bonus_de_acessos_tem_teto_de_015():
    memoria = _memoria()
    episodio = memoria.registrar_episodio(_episodio("pool"), _resolver()).episodio
    for _ in range(20):
        achado = memoria.consultar_episodios("pedidos-api", "pool")[0]
    assert memoria.obter_episodio("pedidos-api", episodio.id_memoria).acessos == 20
    assert achado.pontuacao == pytest.approx(0.7 * achado.similaridade + 0.2 + 0.15, abs=1e-6)


def test_consulta_incrementa_acessos_so_dos_devolvidos():
    memoria = _memoria()
    for incidente in ("inc-1", "inc-2", "inc-3"):
        memoria.registrar_episodio(_episodio(f"causa {incidente}", incidente), _resolver())
    memoria.consultar_episodios("pedidos-api", "causa", k=1)
    acessos = sorted(e.acessos for e in memoria.listar_episodios("pedidos-api"))
    assert acessos == [0, 0, 1]


def test_listar_nao_conta_acesso():
    memoria = _memoria()
    memoria.registrar_episodio(_episodio(), _resolver())
    memoria.listar_episodios("pedidos-api")
    assert memoria.listar_episodios("pedidos-api")[0].acessos == 0


def test_filtro_por_servico():
    memoria = _memoria()
    memoria.registrar_episodio(_episodio("pool", "inc-1", "pedidos-api"), _resolver())
    memoria.registrar_episodio(_episodio("pool", "inc-2", "pagamentos-api"), _resolver())
    achados = memoria.consultar_episodios("pagamentos-api", "pool")
    assert [achado.episodio.incidente_id for achado in achados] == ["inc-2"]
    assert memoria.consultar_episodios("outro-servico", "pool") == []


def test_decaimento_coloca_o_recente_na_frente():
    memoria = _memoria()
    antigo = AGORA - timedelta(days=60)
    memoria.registrar_episodio(_episodio("pool", "velho", criado_em=antigo), _resolver())
    memoria.registrar_episodio(_episodio("pool", "novo"), _resolver("inserir_novo"))
    achados = memoria.consultar_episodios("pedidos-api", "pool")
    assert [achado.episodio.incidente_id for achado in achados] == ["novo", "velho"]
    assert [achado.dias for achado in achados] == [0, 60]


# --- memória semântica -----------------------------------------------------------------------


def test_namespaces_separados():
    memoria = _memoria()
    memoria.registrar_episodio(_episodio("pool", servico="github"), _resolver())
    memoria.registrar_fato_semantico(
        FatoSemantico(assunto="github", fato="pool", fonte="usuario", verificado_em=AGORA)
    )
    assert len(memoria.consultar_episodios("github", "pool")) == 1
    fatos = memoria.consultar_fatos_semanticos("github", "pool")
    assert [fato.fato for fato in fatos] == ["pool"]


def test_fato_vencido_por_valido_ate():
    memoria = _memoria()
    for nome, validade in (("vencido", AGORA - timedelta(days=1)), ("vigente", None)):
        memoria.registrar_fato_semantico(
            FatoSemantico(
                assunto="github",
                fato=nome,
                fonte="documentacao",
                verificado_em=AGORA,
                valido_ate=validade,
            )
        )
    achados = {f.fato: f.vencido for f in memoria.consultar_fatos_semanticos("github", "x")}
    assert achados == {"vencido": True, "vigente": False}


# --- persistência e máscara ------------------------------------------------------------------


def test_salvar_e_carregar_preservam_ativos_e_arquivados(tmp_path):
    arquivo = tmp_path / "memoria.json"
    memoria = _memoria(arquivo)
    antigo = memoria.registrar_episodio(_episodio("deploy v3.2.0"), _resolver()).episodio
    memoria.registrar_episodio(
        _episodio("limite de memória"), _resolver("atualizar_existente", antigo.id_memoria)
    )
    memoria.registrar_fato_semantico(
        FatoSemantico(assunto="github", fato="60/h", fonte="documentacao", verificado_em=AGORA)
    )
    memoria.salvar()
    assert set(json.loads(arquivo.read_text())) == {"episodica", "semantica"}
    outra = MemoriaLongoPrazo.carregar(arquivo, DeterministicFakeEmbedding(size=64), lambda: AGORA)
    ativo = outra.consultar_episodios("pedidos-api", "limite de memória")[0].episodio
    assert ativo.causa == "limite de memória" and ativo.substitui == antigo.id_memoria
    arquivado = outra.obter_episodio("pedidos-api", antigo.id_memoria)
    assert arquivado.status == "arquivado" and arquivado.causa == "deploy v3.2.0"
    assert outra.consultar_fatos_semanticos("github", "60/h")[0].fato == "60/h"


def test_registrar_episodio_salva_sozinho_quando_ha_arquivo(tmp_path):
    arquivo = tmp_path / "memoria.json"
    memoria = _memoria(arquivo)
    assert not arquivo.exists()
    memoria.registrar_episodio(_episodio("deploy v3.2.0"), _resolver())
    assert [e["causa"] for e in json.loads(arquivo.read_text())["episodica"]] == ["deploy v3.2.0"]
    memoria.registrar_fato_semantico(
        FatoSemantico(assunto="github", fato="60/h", fonte="documentacao", verificado_em=AGORA)
    )
    dados = json.loads(arquivo.read_text())
    assert len(dados["episodica"]) == 1 and dados["semantica"][0]["fato"] == "60/h"


def test_consulta_nao_salva_o_incremento_de_acessos(tmp_path):
    arquivo = tmp_path / "memoria.json"
    memoria = _memoria(arquivo)
    memoria.registrar_episodio(_episodio("deploy v3.2.0"), _resolver())
    memoria.consultar_episodios("pedidos-api", "deploy v3.2.0")
    assert json.loads(arquivo.read_text())["episodica"][0]["acessos"] == 0


def test_carregar_nao_reescreve_o_arquivo(tmp_path):
    arquivo = tmp_path / "memoria.json"
    memoria = _memoria(arquivo)
    memoria.registrar_episodio(_episodio("deploy v3.2.0"), _resolver())
    memoria.registrar_fato_semantico(
        FatoSemantico(assunto="github", fato="60/h", fonte="documentacao", verificado_em=AGORA)
    )
    antes = arquivo.read_text()
    MemoriaLongoPrazo.carregar(arquivo, DeterministicFakeEmbedding(size=64), lambda: AGORA)
    assert arquivo.read_text() == antes


def test_sem_arquivo_registrar_nao_escreve_nada(tmp_path):
    _memoria().registrar_episodio(_episodio("deploy v3.2.0"), _resolver())
    assert list(tmp_path.iterdir()) == []


def test_carregar_arquivo_inexistente_devolve_memoria_vazia(tmp_path):
    outra = MemoriaLongoPrazo.carregar(tmp_path / "nao.json", DeterministicFakeEmbedding(size=8))
    assert outra.consultar_episodios("x", "y") == []


def test_texto_com_segredo_e_guardado_mascarado():
    memoria = _memoria()
    memoria.registrar_episodio(
        _episodio(
            "senha=abc123 vazou", evidencia="token=xyz789 no log", resumo="api_key=k9 exposta"
        ),
        _resolver(),
    )
    episodio = memoria.consultar_episodios("pedidos-api", "vazou")[0].episodio
    assert "abc123" not in episodio.causa and "xyz789" not in episodio.evidencia
    assert "k9" not in episodio.resumo and "[SEGREDO]" in episodio.causa


def test_embeddings_padrao_usa_modelo_pequeno(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-teste-nao-usado")
    assert embeddings_padrao().model == "text-embedding-3-small"


# --- InMemoryVectorStore ---------------------------------------------------------------------


class _EmbeddingsContados(DeterministicFakeEmbedding):
    """Conta as chamadas de embedding, para provar que ler/atualizar não reembeda."""

    chamadas: int = 0

    def embed_documents(self, texts):
        self.chamadas += 1
        return super().embed_documents(texts)

    def embed_query(self, text):
        self.chamadas += 1
        return super().embed_query(text)


def test_store_e_vetorial_e_o_documento_episodico_carrega_o_metadata():
    memoria = _memoria()
    episodio = memoria.registrar_episodio(_episodio(evidencia="log"), _resolver()).episodio
    assert isinstance(memoria._store, InMemoryVectorStore)
    documento = memoria._store.get_by_ids([episodio.id_memoria])[0]
    assert documento.id == episodio.id_memoria
    meta = documento.metadata
    assert meta["tipo"] == "episodica"
    assert meta["id_memoria"] == episodio.id_memoria
    assert (meta["incidente_id"], meta["servico"], meta["session_id"]) == (
        "inc-1",
        "pedidos-api",
        "t-1",
    )
    assert (meta["status"], meta["acessos"], meta["substitui"]) == ("ativo", 0, None)
    assert meta["criado_em"].startswith("2026-11-02")


def test_busca_episodica_nunca_devolve_documento_semantico():
    memoria = _memoria()
    memoria.registrar_episodio(_episodio("pool esgotado"), _resolver())
    memoria.registrar_fato_semantico(
        FatoSemantico(
            assunto="pedidos-api", fato="pool esgotado", fonte="documentacao", verificado_em=AGORA
        )
    )
    achados = memoria.consultar_episodios("pedidos-api", "pool esgotado")
    assert len(achados) == 1 and achados[0].episodio.causa == "pool esgotado"
    fatos = memoria.consultar_fatos_semanticos("pedidos-api", "pool esgotado", k=10)
    assert [f.fato for f in fatos] == ["pool esgotado"]
    assert {d["metadata"]["tipo"] for d in memoria._store.store.values()} == {
        "episodica",
        "semantica",
    }


def test_acessos_persistem_no_store_sem_reembedar():
    embeddings = _EmbeddingsContados(size=64)
    memoria = MemoriaLongoPrazo(embeddings, None, lambda: AGORA)
    episodio = memoria.registrar_episodio(_episodio(), _resolver()).episodio
    antes = embeddings.chamadas
    memoria.consultar_episodios("pedidos-api", "pool")
    depois_da_busca = embeddings.chamadas
    memoria.listar_episodios("pedidos-api")
    memoria.obter_episodio("pedidos-api", episodio.id_memoria)
    assert depois_da_busca == antes + 1  # só o embedding da consulta
    assert embeddings.chamadas == depois_da_busca
    guardado = memoria._store.get_by_ids([episodio.id_memoria])[0]
    assert guardado.metadata["acessos"] == 1
    assert memoria.obter_episodio("pedidos-api", episodio.id_memoria).acessos == 1


def test_arquivado_continua_no_store_mas_nao_volta_na_busca():
    memoria = _memoria()
    antigo = memoria.registrar_episodio(_episodio("deploy v3.2.0"), _resolver()).episodio
    novo = memoria.registrar_episodio(
        _episodio("limite de memória"), _resolver("atualizar_existente", antigo.id_memoria)
    ).episodio
    docs = {d.id: d for d in memoria._store.get_by_ids([antigo.id_memoria, novo.id_memoria])}
    assert docs[antigo.id_memoria].metadata["status"] == "arquivado"
    assert docs[novo.id_memoria].metadata["substitui"] == antigo.id_memoria
    achados = memoria.consultar_episodios("pedidos-api", "deploy v3.2.0")
    assert [a.episodio.id_memoria for a in achados] == [novo.id_memoria]
