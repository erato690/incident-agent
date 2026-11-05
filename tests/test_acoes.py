"""sugerir_acao: ferramenta semântica (LLM dentro da ferramenta), nunca executa."""

from pathlib import Path

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.runnables import RunnableLambda

from agente.acoes import SISTEMA_ACAO, montar_ferramenta_acao
from agente.ferramentas import CHAVE_CONTEXTO, PREFIXO
from agente.recuperacao import carregar_indice, construir_indice
from agente.schemas import AcaoSugerida, ContextoTurno, ListaAcoes

PASTA = Path(__file__).resolve().parent.parent / "dados" / "documentos"


class LlmFalso:
    """Suporta `with_structured_output`; guarda as mensagens recebidas."""

    def __init__(self, acoes: list[AcaoSugerida] | None = None):
        self.acoes = acoes or [AcaoSugerida(acao="Reverter o deploy", motivo="bug", risco="baixo")]
        self.recebidos = []

    def with_structured_output(self, schema):
        assert schema is ListaAcoes

        def responde(valor):
            self.recebidos.append(valor.to_messages())
            return ListaAcoes(acoes=self.acoes)

        return RunnableLambda(responde)


@pytest.fixture
def indice(tmp_path):
    embeddings = DeterministicFakeEmbedding(size=64)
    construir_indice(embeddings, tmp_path / "indice", PASTA)
    return carregar_indice(tmp_path / "indice", embeddings)


def _config():
    contexto = ContextoTurno()
    return {"configurable": {CHAVE_CONTEXTO: contexto}}, contexto


def test_sistema_em_ingles_termina_com_a_regra_de_idioma():
    assert SISTEMA_ACAO.rstrip().endswith("Always answer in Brazilian Portuguese.")
    assert "never execute" in " ".join(SISTEMA_ACAO.lower().split())


def test_sugestao_nao_executada_com_status_forcado_e_contexto(indice):
    llm = LlmFalso(
        [
            AcaoSugerida(
                acao="Reverter", motivo="m", risco="baixo", status="sugerida (não executada)"
            )
        ]
    )
    ferramenta = montar_ferramenta_acao(llm, indice)
    config, contexto = _config()
    saida = ferramenta.invoke(
        {"diagnostico": "NullPointerException após deploy", "servico": "pedidos-api"}, config
    )
    assert saida.startswith(PREFIXO)
    assert "SUGESTÃO, NÃO EXECUTADA:" in saida and "Reverter" in saida
    assert [a.status for a in contexto.acoes_sugeridas] == ["sugerida (não executada)"]
    assert contexto.acoes_sugeridas[0].runbook  # preenchido com o título do runbook


def test_runbook_ja_informado_e_preservado_e_contexto_e_substituido(indice):
    llm = LlmFalso([AcaoSugerida(acao="A", motivo="m", risco="medio", runbook="Meu runbook")])
    ferramenta = montar_ferramenta_acao(llm, indice)
    config, contexto = _config()
    contexto.acoes_sugeridas = [AcaoSugerida(acao="antiga", motivo="m", risco="alto")]
    ferramenta.invoke({"diagnostico": "d", "servico": "s"}, config)
    assert [(a.acao, a.runbook) for a in contexto.acoes_sugeridas] == [("A", "Meu runbook")]


def test_runbook_entra_no_prompt_como_dado_e_funciona_sem_contexto(indice):
    llm = LlmFalso()
    ferramenta = montar_ferramenta_acao(llm, indice)
    saida = ferramenta.invoke({"diagnostico": "pool de conexões esgotado", "servico": "s"})
    assert "SUGESTÃO, NÃO EXECUTADA:" in saida
    sistema, humana = llm.recebidos[0]
    assert sistema.content.rstrip().endswith("Always answer in Brazilian Portuguese.")
    assert "pool de conexões esgotado" in humana.content


def test_erro_do_modelo_vira_texto_legivel(indice):
    class Quebrado:
        def with_structured_output(self, schema):
            return RunnableLambda(lambda _: (_ for _ in ()).throw(RuntimeError("falhou")))

    saida = montar_ferramenta_acao(Quebrado(), indice).invoke({"diagnostico": "d", "servico": "s"})
    assert "Tool error" in saida and "falhou" in saida
