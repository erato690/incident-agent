"""Ferramentas de memória: consultar_memoria, gravar_episodio com trava e regras no prompt."""

import re
from datetime import datetime
from pathlib import Path

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding, Embeddings
from langchain_core.runnables import RunnableLambda

from agente.agente_react import (
    montar_investigador,
    montar_registrador,
    montar_sistema_agente,
)
from agente.ferramentas import PREFIXO, montar_ferramentas, montar_ferramentas_memoria
from agente.loja import FonteLoja
from agente.memoria import MemoriaLongoPrazo
from agente.schemas import ContextoTurno, Episodio, ResolucaoMemoria
from tests.fakes import chamada, roteiro
from tests.test_agente_react import JSON_OK

RAIZ = Path(__file__).parent / "dados"
AGORA = datetime(2026, 11, 2, 12, 0)
RECUSA = "Só gravo causa confirmada explicitamente pelo engenheiro; nada foi gravado."
ARGUMENTOS = {
    "resumo": "500 no checkout; a investigação viu o pool no teto",
    "causa": "pool de conexões esgotado",
    "evidencia": "HikariPool no log",
    "levantada_pelo_agente": True,
}


def _memoria():
    return MemoriaLongoPrazo(DeterministicFakeEmbedding(size=64), agora=lambda: AGORA)


def _resolvedor(acao="inserir_novo"):
    def decide(entrada):
        antigo = re.search(r"ID: (\S+)", entrada["existentes"]).group(1)
        return ResolucaoMemoria(acao=acao, id_memoria_antiga=antigo, motivo="decisão do teste")

    return RunnableLambda(decide)


def _ferramentas(memoria=None, resolvedor=None):
    fonte = FonteLoja.gravada("cenario_teste", raiz=RAIZ)
    return {f.name: f for f in montar_ferramentas(fonte, memoria=memoria, resolver=resolvedor)}


def _config(**campos):
    contexto = ContextoTurno(**campos)
    return {"configurable": {"contexto_turno": contexto}}, contexto


def _confirmacao(**extra):
    base = {
        "intencao": "confirmar_causa",
        "servico": "pedidos-api",
        "incidente_id": "inc-1",
        "session_id": "t-1",
    }
    return _config(**{**base, **extra})


def _gravar(ferramentas, config, argumentos=ARGUMENTOS):
    return ferramentas["gravar_episodio"].invoke(argumentos, config=config)


# --- consultar_memoria -------------------------------------------------------------------------


def test_com_memoria_inclui_as_duas_ferramentas_de_memoria():
    ferramentas = _ferramentas(_memoria(), _resolvedor())
    assert set(ferramentas["consultar_memoria"].args) == {"servico", "descricao"}
    assert set(ferramentas["gravar_episodio"].args) == set(ARGUMENTOS)


def test_sem_memoria_nao_inclui_nenhuma():
    ferramentas = _ferramentas()
    assert "consultar_memoria" not in ferramentas and "gravar_episodio" not in ferramentas


def test_sem_resolvedor_so_consulta():
    ferramentas = _ferramentas(_memoria())
    assert "consultar_memoria" in ferramentas and "gravar_episodio" not in ferramentas


def test_observacao_marca_historico_e_prefixo():
    memoria = _memoria()
    memoria.registrar_episodio(
        Episodio(
            incidente_id="inc-7",
            session_id="t",
            servico="pedidos-api",
            resumo="500 no checkout",
            causa="pool de conexões esgotado",
            origem="engenheiro",
            criado_em=AGORA,
        ),
        _resolvedor(),
    )
    saida = _ferramentas(memoria)["consultar_memoria"].invoke(
        {"servico": "pedidos-api", "descricao": "pool de conexões esgotado"}
    )
    assert saida.startswith(PREFIXO)
    assert "HISTÓRICO (não é observação atual): incidente inc-7 em 2026-11-02" in saida
    assert "pool de conexões esgotado (pontuação" in saida


def test_memoria_vazia_responde_nenhum_incidente():
    saida = _ferramentas(_memoria())["consultar_memoria"].invoke(
        {"servico": "pedidos-api", "descricao": "pool"}
    )
    assert "Nenhum incidente confirmado parecido o bastante" in saida
    assert "0.55" in saida and "pedidos-api" in saida


def test_regras_de_memoria_no_prompt_so_quando_a_ferramenta_existe():
    com = montar_sistema_agente(list(_ferramentas(_memoria(), _resolvedor()).values()))
    sem = montar_sistema_agente(list(_ferramentas().values()))
    assert "consultar_memoria" in com and "consultar_memoria" not in sem
    assert "gravar_episodio" in com and "gravar_episodio" not in sem
    assert com.rstrip().endswith("Always answer in Brazilian Portuguese.")


def test_regra_de_memoria_exige_citar_episodio_como_historico():
    com = montar_sistema_agente(list(_ferramentas(_memoria()).values()))
    sem = montar_sistema_agente(list(_ferramentas().values()))
    assert "(histórico, não é observação atual)" in com
    assert "consultar_memoria: incidente <id> em <data>: <causa>" in com
    assert "no confirmed incident" in com
    assert "(histórico, não é observação atual)" not in sem


# --- gravar_episodio: a trava ------------------------------------------------------------------


def test_grava_na_confirmacao_com_servico_e_incidente_do_contexto():
    memoria = _memoria()
    config, contexto = _confirmacao()
    saida = _gravar(_ferramentas(memoria, _resolvedor()), config)
    assert saida.startswith(PREFIXO) and "inserir_novo" in saida
    episodio = contexto.registro.episodio
    assert (episodio.servico, episodio.incidente_id, episodio.session_id) == (
        "pedidos-api",
        "inc-1",
        "t-1",
    )
    assert episodio.origem == "agente" and episodio.resumo == ARGUMENTOS["resumo"]
    assert memoria.listar_episodios("pedidos-api") == [episodio]


def test_recusa_quando_a_intencao_nao_e_confirmar_causa():
    memoria = _memoria()
    config, contexto = _confirmacao(intencao="investigar_erro")
    saida = _gravar(_ferramentas(memoria, _resolvedor()), config)
    assert RECUSA in saida and contexto.registro is None
    assert memoria.listar_episodios("pedidos-api") == []


def test_recusa_sem_servico_sem_incidente_ou_sem_contexto():
    memoria = _memoria()
    ferramentas = _ferramentas(memoria, _resolvedor())
    for config in (_confirmacao(servico=None)[0], _confirmacao(incidente_id=None)[0], {}):
        assert RECUSA in _gravar(ferramentas, config)
    assert memoria.listar_episodios("pedidos-api") == []


def test_o_modelo_nao_escolhe_servico_nem_incidente():
    campos = _ferramentas(_memoria(), _resolvedor())["gravar_episodio"].args
    assert "servico" not in campos and "incidente_id" not in campos and "session_id" not in campos


def test_segunda_gravacao_no_mesmo_turno_e_ignorada():
    memoria = _memoria()
    config, _ = _confirmacao()
    ferramentas = _ferramentas(memoria, _resolvedor())
    _gravar(ferramentas, config)
    assert "já" in _gravar(ferramentas, config)
    assert len(memoria.listar_episodios("pedidos-api")) == 1


def test_erro_do_resolvedor_vira_observacao_e_nada_e_gravado():
    def quebra(entrada):
        raise RuntimeError("modelo fora do ar")

    memoria = _memoria()
    config, contexto = _confirmacao()
    ferramentas = _ferramentas(memoria, RunnableLambda(quebra))
    memoria.registrar_episodio(
        Episodio(
            incidente_id="inc-0",
            session_id="t",
            servico="pedidos-api",
            resumo="r",
            causa="c",
            origem="engenheiro",
            criado_em=AGORA,
        ),
        _resolvedor(),
    )
    saida = _gravar(ferramentas, config)
    assert "modelo fora do ar" in saida and contexto.registro is None
    assert len(memoria.listar_episodios("pedidos-api")) == 1


def test_segredo_no_argumento_e_mascarado_ao_gravar():
    memoria = _memoria()
    config, contexto = _confirmacao()
    _gravar(_ferramentas(memoria, _resolvedor()), config, {**ARGUMENTOS, "causa": "senha=abc123"})
    assert "abc123" not in contexto.registro.episodio.causa


# --- a trava vale para o Investigador ------------------------------------------------


def test_agente_de_investigacao_tentando_gravar_hipotese_e_recusado():
    memoria = _memoria()
    ferramentas = list(_ferramentas(memoria, _resolvedor()).values())
    modelo = roteiro(chamada("gravar_episodio", ARGUMENTOS), JSON_OK)
    agente = montar_investigador(modelo, ferramentas)
    config, contexto = _confirmacao(intencao="investigar_erro")
    resultado = agente.invoke({"mensagem": "acho que é o pool", "historico": []}, config=config)
    assert resultado.erro is None and resultado.trajetoria[0].ferramenta == "gravar_episodio"
    observacao = [m for m in modelo.chamadas[-1] if getattr(m, "type", "") == "tool"][-1]
    assert RECUSA in observacao.content
    assert contexto.registro is None and memoria.listar_episodios("pedidos-api") == []


def test_agente_de_registro_grava_quando_o_turno_e_confirmacao():
    memoria = _memoria()
    ferramentas = list(_ferramentas(memoria, _resolvedor()).values())
    modelo = roteiro(chamada("gravar_episodio", ARGUMENTOS), "Registrei a causa.")
    agente = montar_registrador(modelo, ferramentas)
    config, contexto = _confirmacao()
    texto = agente.invoke({"mensagem": "confirmado: foi o pool", "historico": []}, config=config)
    assert texto == "Registrei a causa." and contexto.registro.episodio.causa == ARGUMENTOS["causa"]
    assert len(memoria.listar_episodios("pedidos-api")) == 1


def test_prompt_do_agente_de_registro_e_em_ingles_e_manda_chamar_a_ferramenta():
    modelo = roteiro("ok")
    montar_registrador(modelo, list(_ferramentas(_memoria(), _resolvedor()).values())).invoke(
        {"mensagem": "confirmado", "historico": []}, config=_confirmacao()[0]
    )
    sistema = modelo.chamadas[0][0].content
    assert "gravar_episodio" in sistema and "confirmed" in sistema
    assert sistema.rstrip().endswith("Always answer in Brazilian Portuguese.")


# --- limiar de similaridade (D8) e regras do prompt ---------------------------------------------


class EmbeddingEscolhido(Embeddings):
    """Vetor 2D escolhido por texto: 'perto' tem cosseno 1 com a consulta; 'longe', cerca de 0,3."""

    VETORES = {"consulta": [1.0, 0.0], "perto": [1.0, 0.0], "longe": [0.3, 0.954]}

    def embed_query(self, texto):
        chave = next((k for k in self.VETORES if k in texto), None)
        return self.VETORES.get(chave, [0.0, 1.0])

    def embed_documents(self, textos):
        return [self.embed_query(t) for t in textos]


def _memoria_com_dois():
    memoria = MemoriaLongoPrazo(EmbeddingEscolhido(), agora=lambda: AGORA)
    for nome in ("perto", "longe"):
        memoria._gravar_episodio(
            Episodio(
                id_memoria=nome,
                incidente_id=f"inc-{nome}",
                session_id="t-x",
                servico="pedidos-api",
                resumo=nome,
                causa=f"causa {nome}",
                origem="engenheiro",
                criado_em=AGORA,
            )
        )
    return memoria


@pytest.mark.limiar_real
def test_limiar_descarta_abaixo_e_nao_soma_acesso():
    memoria = _memoria_com_dois()
    achados = memoria.consultar_episodios("pedidos-api", "consulta")
    assert [a.episodio.id_memoria for a in achados] == ["perto"]
    assert memoria.obter_episodio("pedidos-api", "perto").acessos == 1
    assert memoria.obter_episodio("pedidos-api", "longe").acessos == 0


@pytest.mark.limiar_real
def test_limiar_pode_ser_ajustado():
    memoria = _memoria_com_dois()
    achados = memoria.consultar_episodios("pedidos-api", "consulta", similaridade_minima=0.2)
    assert {a.episodio.id_memoria for a in achados} == {"perto", "longe"}


@pytest.mark.limiar_real
def test_ferramenta_com_tudo_abaixo_diz_que_nada_e_parecido():
    memoria = _memoria_com_dois()
    memoria._store.delete(["perto"])
    saida = _ferramentas(memoria)["consultar_memoria"].invoke(
        {"servico": "pedidos-api", "descricao": "consulta"}
    )
    assert "Nenhum incidente confirmado parecido o bastante" in saida and "0.55" in saida
    assert memoria.obter_episodio("pedidos-api", "longe").acessos == 0


def test_regras_de_confianca_e_exemplo_so_com_a_ferramenta_de_memoria():
    com = montar_sistema_agente(list(_ferramentas(_memoria(), _resolvedor()).values()))
    sem = montar_sistema_agente(list(_ferramentas().values()))
    com, sem = " ".join(com.split()), " ".join(sem.split())
    for trecho in ("main error message from the logs", "is only context", "statement timeout"):
        assert trecho in com and trecho not in sem
    assert com.rstrip().endswith("Always answer in Brazilian Portuguese.")


# --- reforço para o modelo chamar a memória depois dos logs, com a mensagem de erro -----------


def test_descricao_da_ferramenta_exige_logs_antes_e_erro_principal():
    ferramenta = _ferramentas(_memoria())["consultar_memoria"]
    assert "Call ONLY after buscar_logs" in ferramenta.description
    assert "MUST contain the symptom AND the main error message" in ferramenta.description
    assert "never a vague text" in ferramenta.description
    argumento = ferramenta.args["descricao"]["description"]
    assert "main error message" in argumento and "buscar_logs" in argumento


def test_regra_de_memoria_manda_investigar_antes_de_consultar():
    prompt = montar_sistema_agente(list(_ferramentas(_memoria()).values()))
    assert "first investigate with the store tools (at least buscar_logs)" in prompt
    assert "never answer with the memory alone" in prompt
    assert prompt.rstrip().endswith("Always answer in Brazilian Portuguese.")


# --- limiar configurável na fábrica -------------------------------------------------------------


def _memoria_com_episodio():
    memoria = _memoria()
    memoria.registrar_episodio(
        Episodio(
            incidente_id="inc-7",
            session_id="t-1",
            servico="pedidos-api",
            resumo="500 no checkout",
            causa="pool de conexões esgotado",
            origem="engenheiro",
            criado_em=AGORA,
        ),
        _resolvedor(),
    )
    return memoria


def _consulta(**fabrica):
    fonte = FonteLoja.gravada("cenario_teste", raiz=RAIZ)
    ferramentas = montar_ferramentas(fonte, memoria=_memoria_com_episodio(), **fabrica)
    consultar = next(f for f in ferramentas if f.name == "consultar_memoria")
    return consultar.invoke({"servico": "pedidos-api", "descricao": "texto sem relação nenhuma"})


@pytest.mark.limiar_real
def test_limiar_padrao_descarta_texto_sem_semantica():
    assert "Nenhum incidente confirmado parecido o bastante" in _consulta()


@pytest.mark.limiar_real
def test_limiar_zero_na_fabrica_devolve_o_episodio():
    saida = _consulta(similaridade_minima=0.0)
    assert "incidente inc-7" in saida


def test_fabrica_de_memoria_aceita_o_limiar_e_a_mensagem_mostra_o_valor():
    consultar = montar_ferramentas_memoria(_memoria(), similaridade_minima=0.9)[0]
    saida = consultar.invoke({"servico": "pedidos-api", "descricao": "x"})
    assert "0.90" in saida
