"""Agente integrado com fakes: registro, post-mortem, consultar_sql e agente clássico."""

from datetime import datetime
from pathlib import Path

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.runnables import RunnableLambda

from agente.integrado import (
    CATEGORIA_SEM_CONFIRMACAO,
    TEXTO_SEM_ANALISE,
    AgenteIntegrado,
    montar_agente_classico,
    montar_agente_integrado,
)
from agente.memoria import MemoriaLongoPrazo
from agente.recuperacao import carregar_indice, construir_indice
from agente.schemas import (
    AnaliseNLU,
    Episodio,
    PassoTrajetoria,
    ResolucaoMemoria,
    ResultadoInvestigacao,
)
from agente.sql import BancoSQL
from scripts.construir_sqlite import construir
from tests.fakes import chamada, roteiro
from tests.test_roteamento import ANALISE

DOCS = Path(__file__).resolve().parent.parent / "dados" / "documentos"
PASSO = PassoTrajetoria(
    ferramenta="buscar_logs", argumentos={"servico": "x"}, duracao_ms=1, tamanho=9
)


def _nlu(entrada):
    texto = entrada["mensagem"].lower()
    intencao = "gerar_relatorio" if "post-mortem" in texto else "investigar_erro"
    return AnaliseNLU(intencao=intencao, servico="pagamentos-api")


def _investigacao(entrada):
    return ResultadoInvestigacao(analise=ANALISE, trajetoria=[PASSO])


@pytest.fixture
def agente(tmp_path):
    embeddings = DeterministicFakeEmbedding(size=64)
    construir_indice(embeddings, tmp_path / "indice", DOCS)
    return montar_agente_integrado(
        roteiro("ok"),
        embeddings=embeddings,
        indice=carregar_indice(tmp_path / "indice", embeddings),
        banco=BancoSQL(construir(tmp_path / "i.db")),
        memoria=MemoriaLongoPrazo(embeddings, tmp_path / "memoria.json"),
        auditor=False,
        avaliar_relevancia=False,
        pasta_postmortem=tmp_path / "saida",
        nlu=RunnableLambda(_nlu),
        investigacao=RunnableLambda(_investigacao),
    )


def test_fabrica_devolve_agente_integrado(agente):
    assert isinstance(agente, AgenteIntegrado)
    assert agente.registro.listar() == []


def test_turno_investiga_e_grava_registro(agente):
    sessao = agente.abrir_sessao("pool_esgotado", "INC-1")
    resposta = agente.turno(sessao, "pagamentos-api com NullPointerException")
    assert resposta.rota == "investigacao"
    (turno,) = agente.registro.listar(sessao.session_id)
    assert turno.rota == "investigacao" and turno.cenario == "pool_esgotado"
    assert turno.incidente_id == "INC-1" and turno.ferramentas == ["buscar_logs"]
    assert turno.duracao_ms >= 0 and sessao.turnos == 1


def test_postmortem_sem_causa_confirmada_nao_gera_e_pede_confirmacao(agente, tmp_path):
    sessao = agente.abrir_sessao("pool_esgotado")
    agente.turno(sessao, "pagamentos-api com NullPointerException")
    resposta = agente.turno(sessao, "gere o post-mortem")
    assert resposta.rota == "fixa" and resposta.fixa.categoria == CATEGORIA_SEM_CONFIRMACAO
    assert not (tmp_path / "saida").exists()
    texto = resposta.fixa.texto
    assert "falta confirmar a causa" in texto and ANALISE.hipoteses[0].causa in texto
    assert "Confirmado:" in texto and "?" in texto


def _confirmar(agente, sessao):
    agente.memoria.registrar_episodio(
        Episodio(
            incidente_id=sessao.session_id,
            session_id=sessao.session_id,
            servico="pagamentos-api",
            resumo="Cupom nulo",
            causa="cupom nulo no checkout",
            origem="engenheiro",
            criado_em=datetime.now(),
        ),
        RunnableLambda(lambda _: ResolucaoMemoria(acao="inserir_novo", motivo="novo")),
    )


def test_postmortem_com_causa_confirmada_gera_arquivo(agente, tmp_path):
    sessao = agente.abrir_sessao("pool_esgotado")
    agente.turno(sessao, "pagamentos-api com NullPointerException")
    _confirmar(agente, sessao)
    resposta = agente.turno(sessao, "gere o post-mortem")
    assert resposta.fixa.categoria == "gerar_relatorio"
    arquivo = tmp_path / "saida" / f"postmortem_{sessao.session_id}.md"
    assert arquivo.exists() and str(arquivo) in resposta.fixa.texto
    conteudo = arquivo.read_text(encoding="utf-8")
    assert "causa não confirmada" not in conteudo and "## Lições aprendidas" in conteudo


def test_postmortem_usa_episodio_confirmado(agente, tmp_path):
    sessao = agente.abrir_sessao("pool_esgotado")
    agente.turno(sessao, "pagamentos-api com NullPointerException")
    _confirmar(agente, sessao)
    resposta = agente.turno(sessao, "gere o post-mortem")
    assert "Causa confirmada: cupom nulo no checkout" in resposta.fixa.texto


def test_postmortem_sem_investigacao(agente, tmp_path):
    sessao = agente.abrir_sessao("pool_esgotado")
    resposta = agente.turno(sessao, "gere o post-mortem")
    assert resposta.fixa.texto == TEXTO_SEM_ANALISE
    assert not (tmp_path / "saida").exists()


def test_consultar_sql_entra_nas_ferramentas(agente):
    nomes = [f.name for f in agente.ferramentas("pool_esgotado")]
    assert "consultar_sql" in nomes and "buscar_logs" in nomes
    sql = next(f for f in agente.ferramentas("pool_esgotado") if f.name == "consultar_sql")
    assert "incidentes(" in sql.description


def test_regra_sql_so_com_a_ferramenta(agente):
    from agente.agente_react import montar_sistema_agente

    ferramentas = agente.ferramentas("pool_esgotado")
    assert "SQL rule" in montar_sistema_agente(ferramentas)
    sem = [f for f in ferramentas if f.name != "consultar_sql"]
    assert "SQL rule" not in montar_sistema_agente(sem)


def test_agente_classico_constroi_e_invoca(agente):
    ferramentas = agente.ferramentas("pool_esgotado")
    modelo = roteiro(
        chamada("consultar_sql", {"query": "SELECT COUNT(*) FROM incidentes"}), "Há incidentes."
    )
    executor = montar_agente_classico(modelo, ferramentas)
    saida = executor.invoke({"input": "Quantos incidentes?"})
    assert saida["output"] == "Há incidentes."
    assert saida["intermediate_steps"][0][0].tool == "consultar_sql"


def test_postmortem_ignora_resposta_que_so_consultou_o_sql(agente, tmp_path):
    """Pergunta de histórico (só consultar_sql) não substitui a investigação do incidente."""
    from agente.schemas import AnaliseIncidente

    sessao = agente.abrir_sessao("pool_esgotado")
    agente.turno(sessao, "pagamentos-api com NullPointerException")
    so_sql = ResultadoInvestigacao(
        analise=AnaliseIncidente.model_validate(
            {**ANALISE.model_dump(exclude={"acoes_sugeridas"}), "resumo": "contagem do SQL"}
        ),
        trajetoria=[PASSO.model_copy(update={"ferramenta": "consultar_sql"})],
    )
    agente._guardar(sessao, RespostaTurnoFalsa.de(so_sql))
    _confirmar(agente, sessao)
    texto = agente.turno(sessao, "gere o post-mortem").fixa.texto
    assert "contagem do SQL" not in texto and ANALISE.resumo in texto


class RespostaTurnoFalsa:
    @staticmethod
    def de(resultado):
        from agente.schemas import AnaliseNLU, RespostaTurno, ResultadoModeracao

        return RespostaTurno(
            rota="investigacao",
            moderacao=ResultadoModeracao(status="ok"),
            nlu=AnaliseNLU(intencao="investigar_erro", servico="pagamentos-api"),
            analise=resultado.analise,
            trajetoria=resultado.trajetoria,
        )
