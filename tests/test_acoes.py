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


def test_runbook_inventado_vira_o_titulo_recuperado_e_contexto_e_substituido(indice):
    """Título que não veio da busca (ex.: corrompido pelo modelo) é trocado pelo recuperado."""
    llm = LlmFalso([AcaoSugerida(acao="A", motivo="m", risco="medio", runbook="db-principal},{")])
    ferramenta = montar_ferramenta_acao(llm, indice)
    config, contexto = _config()
    contexto.acoes_sugeridas = [AcaoSugerida(acao="antiga", motivo="m", risco="alto")]
    ferramenta.invoke({"diagnostico": "d", "servico": "s"}, config)
    assert [a.acao for a in contexto.acoes_sugeridas] == ["A"]
    assert contexto.acoes_sugeridas[0].runbook.startswith(("Runbook", "Limites", "Política"))


def test_runbook_recuperado_informado_pelo_modelo_e_preservado(indice):
    from agente.recuperacao import buscar_com_score

    titulos = [
        d.metadata["titulo"]
        for d, _ in buscar_com_score(indice, "d", k=2, filtro={"tipo": "runbook"})
    ]
    llm = LlmFalso([AcaoSugerida(acao="A", motivo="m", risco="baixo", runbook=titulos[-1])])
    config, contexto = _config()
    montar_ferramenta_acao(llm, indice).invoke({"diagnostico": "d", "servico": "s"}, config)
    assert contexto.acoes_sugeridas[0].runbook == titulos[-1]


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


class LlmEmSequencia(LlmFalso):
    """Devolve uma lista de ações por chamada, na ordem."""

    def __init__(self, *listas):
        super().__init__()
        self.listas = list(listas)

    def with_structured_output(self, schema):
        def responde(valor):
            self.recebidos.append(valor.to_messages())
            return ListaAcoes(acoes=self.listas.pop(0))

        return RunnableLambda(responde)


def _acao(texto):
    return AcaoSugerida(acao=texto, motivo="m", risco="baixo")


def test_acao_de_consulta_e_recusada_e_o_modelo_tenta_de_novo(indice):
    llm = LlmEmSequencia(
        [_acao("Verifique os logs para identificar o volume"), _acao("Consulte a wiki")],
        [_acao("Respeitar o Retry-After de 30 s com backoff exponencial")],
    )
    ferramenta = montar_ferramenta_acao(llm, indice)
    config, contexto = _config()
    saida = ferramenta.invoke(
        {"diagnostico": "limite de 100/min excedido", "servico": "pagamentos-api"}, config=config
    )
    assert [a.acao for a in contexto.acoes_sugeridas] == [
        "Respeitar o Retry-After de 30 s com backoff exponencial"
    ]
    assert "Verifique os logs" not in saida and len(llm.recebidos) == 2
    correcao = llm.recebidos[1][-1].content
    assert "Verifique os logs para identificar o volume" in correcao


def test_sem_acao_concreta_apos_nova_tentativa_fica_so_o_que_presta(indice):
    llm = LlmEmSequencia(
        [_acao("Verifique os logs"), _acao("Limitar as chamadas a 90 por minuto")],
        [_acao("Checar as métricas")],
    )
    ferramenta = montar_ferramenta_acao(llm, indice)
    config, contexto = _config()
    ferramenta.invoke({"diagnostico": "d", "servico": "s"}, config=config)
    assert [a.acao for a in contexto.acoes_sugeridas] == ["Limitar as chamadas a 90 por minuto"]


def test_sistema_de_acao_proibe_acao_de_consulta_e_pede_o_numero():
    texto = " ".join(SISTEMA_ACAO.split())
    assert "never an action that only checks" in texto and "number" in texto
