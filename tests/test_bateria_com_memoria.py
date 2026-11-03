"""Bateria com memória: sessão por conversa, colunas e dados (sem modelo real)."""

import json
import re
from datetime import datetime
from pathlib import Path

from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.runnables import RunnableLambda

from agente.agente_react import montar_investigador
from agente.bateria import detalhe_html, linhas_bateria, rodar_bateria, rodar_conversa_sessao
from agente.conversa import abrir_sessao, montar_conversa
from agente.ferramentas import montar_ferramentas
from agente.loja import FonteLoja
from agente.memoria import MemoriaLongoPrazo
from agente.pipeline import montar_pipeline
from agente.schemas import (
    AnaliseNLU,
    Episodio,
    PassoTrajetoria,
    ResolucaoMemoria,
    RespostaFixa,
    RespostaTurno,
    ResultadoModeracao,
)
from tests.fakes import chamada, roteiro
from tests.test_agente_react import JSON_OK

DADOS = Path(__file__).parent.parent / "dados_dummy"
RAIZ = Path(__file__).parent / "dados"
MENSAGENS = json.loads((DADOS / "fase3_mensagens.json").read_text(encoding="utf-8"))
CONVERSAS = json.loads((DADOS / "fase3_conversas.json").read_text(encoding="utf-8"))
AGORA = datetime(2026, 11, 2, 12, 0)
MODERACAO = ResultadoModeracao(status="ok")


def _moderar(texto):
    return MODERACAO


def _episodio(incidente="inc-1"):
    return Episodio(
        incidente_id=incidente,
        session_id="t-1",
        servico="pedidos-api",
        resumo="500 no checkout",
        causa="deploy",
        origem="engenheiro",
        criado_em=AGORA,
    )


def _resposta(**campos):
    return RespostaTurno(rota="fixa", moderacao=MODERACAO, **campos)


def _passo(ferramenta):
    return PassoTrajetoria(ferramenta=ferramenta, duracao_ms=3, tamanho=9)


def _turnos(conversa: dict) -> list[dict]:
    """Turnos como itens de bateria (o `id` é acrescentado por `exibir_conversa` no notebook)."""
    return [{**turno, "id": f"{conversa['id']}-{i}"} for i, turno in enumerate(conversa["turnos"])]


def _mensagem(**campos):
    return {"id": "a", "grupo": "memoria", "mensagem": "m", "rota_esperada": "fixa", **campos}


# --- dados da fase ---------------------------------------------------------------------------


def test_dados_fase3_bem_formados():
    cenarios = {arquivo.stem for arquivo in (DADOS / "cenarios").glob("*.json")}
    assert len(MENSAGENS) >= 8
    for mensagem in MENSAGENS:
        assert {"id", "mensagem", "rota_esperada", "intencao_esperada"} <= mensagem.keys()
        assert isinstance(mensagem["registra_esperado"], bool)
        assert mensagem.get("cenario", "pool_esgotado") in cenarios
    assert {m["registra_esperado"] for m in MENSAGENS} == {True, False}
    assert [c["id"] for c in CONVERSAS] == [
        "confirmacao_e_recorrencia",
        "recorrencia_sessao_b",
        "decomposicao",
        "conversa_longa",
        "troca_de_causa",
    ]
    tamanhos = {c["id"]: len(c["turnos"]) for c in CONVERSAS}
    assert tamanhos["decomposicao"] == 4 and tamanhos["conversa_longa"] == 12
    assert all(c["cenario"] in cenarios for c in CONVERSAS)
    assert all({"mensagem", "rota_esperada"} <= t.keys() for c in CONVERSAS for t in c["turnos"])


def test_memoria_de_demonstracao_tem_episodio_antigo():
    memoria = MemoriaLongoPrazo.carregar(
        DADOS / "memoria_longo_prazo.json", DeterministicFakeEmbedding(size=64), lambda: AGORA
    )
    achado = memoria.consultar_episodios("pedidos-api", "pool de conexões")[0]
    assert achado.episodio.servico == "pedidos-api" and achado.episodio.status == "ativo"
    assert achado.dias == 59 and achado.acessos == 0


# --- sessão por conversa -----------------------------------------------------------------------


def _conversa_falsa(vistos: list):
    def pipeline(entrada):
        vistos.append(entrada)
        return _resposta()

    return montar_conversa(RunnableLambda(pipeline), roteiro("RESUMO"))


def test_cada_conversa_abre_sessao_nova_e_o_historico_so_vale_dentro_dela():
    vistos: list = []
    conversa = _conversa_falsa(vistos)
    dados = {"id": "c", "turnos": [{"mensagem": "um"}, {"mensagem": "dois"}]}
    respostas = rodar_conversa_sessao(conversa, dados)
    rodar_conversa_sessao(conversa, dados)
    assert len(respostas) == 2
    assert vistos[0]["incidente_id"] == vistos[1]["incidente_id"] != vistos[2]["incidente_id"]
    assert vistos[0]["historico"] == [] and len(vistos[1]["historico"]) == 2
    assert vistos[2]["historico"] == []


def test_sessao_recebe_cenario_e_pode_ser_inspecionada():
    conversa = _conversa_falsa([])
    sessao = abrir_sessao()
    rodar_conversa_sessao(
        conversa, {"id": "c", "cenario": "pool_esgotado", "turnos": [{"mensagem": "x"}]}, sessao
    )
    assert sessao.turnos == 1
    nova = abrir_sessao()
    assert nova.session_id != sessao.session_id


def test_fabrica_por_cenario_recebe_o_cenario_da_conversa():
    pedidos: list = []

    def fabrica(cenario):
        pedidos.append(cenario)
        return _conversa_falsa([])

    dados = {"id": "c", "cenario": "pool_esgotado", "turnos": [{"mensagem": "x"}]}
    rodar_conversa_sessao(fabrica, dados)
    assert pedidos == ["pool_esgotado"]


def test_rodar_bateria_envia_o_id_da_mensagem_como_incidente():
    vistos: list = []
    pipeline = RunnableLambda(lambda entrada: vistos.append(entrada) or _resposta())
    rodar_bateria(pipeline, [_mensagem()])
    assert vistos[0]["incidente_id"] == "a" and vistos[0]["historico"] == []


# --- colunas de memória --------------------------------------------------------------------------


def test_colunas_de_memoria_registrada_e_consultada():
    mensagens = [_mensagem(id=nome) for nome in "abcd"]
    respostas = [
        _resposta(episodio=_episodio()),
        _resposta(episodio=_episodio(), episodio_anterior=_episodio("inc-0")),
        _resposta(trajetoria=[_passo("buscar_logs"), _passo("consultar_memoria")]),
        _resposta(),
    ]
    linhas = linhas_bateria(mensagens, respostas)
    assert [linha["memória registrada"] for linha in linhas] == [
        "registrado",
        "atualizado",
        "-",
        "-",
    ]
    assert [linha["memória consultada"] for linha in linhas] == ["-", "-", "sim", "-"]


def test_sem_memoria_as_colunas_somem_como_nas_fases_anteriores():
    linha = linhas_bateria([_mensagem()], [_resposta()])[0]
    assert "memória registrada" not in linha and "memória consultada" not in linha


def test_registra_esperado_entra_no_ok():
    com_episodio = _resposta(episodio=_episodio())
    esperado = linhas_bateria([_mensagem(registra_esperado=True)], [com_episodio])[0]
    errado = linhas_bateria([_mensagem(registra_esperado=False)], [com_episodio])[0]
    assert esperado["ok"] and not errado["ok"]
    assert "registra esperado" not in linhas_bateria([_mensagem()], [com_episodio])[0]


def test_detalhe_mostra_o_episodio_registrado():
    resolucao = ResolucaoMemoria(acao="inserir_novo", motivo="incidente novo")
    html = detalhe_html(_mensagem(), _resposta(episodio=_episodio("inc-77"), resolucao=resolucao))
    assert "inc-77" in html and "pedidos-api" in html and "Memória" in html
    assert "inserir_novo" in html and "incidente novo" in html


def test_rota_memoria_rotula_registro_e_episodio():
    fixa = RespostaFixa(texto="Registrei.", camada=2, categoria="causa")
    base = {"moderacao": MODERACAO, "fixa": fixa, "episodio": _episodio()}
    nova = RespostaTurno(rota="memoria", **base)
    html = detalhe_html(_mensagem(rota_esperada="memoria"), nova)
    assert "Registro na memória episódica:" in html and "Resposta fixa" not in html
    assert "Memória: episódio registrado" in html
    atual = RespostaTurno(rota="memoria", episodio_anterior=_episodio("inc-0"), **base)
    html = detalhe_html(_mensagem(rota_esperada="memoria"), atual)
    assert "Memória: episódio atualizado (anterior arquivado)" in html


def test_mensagem_pergunta_causa_cita_o_servico():
    item = next(m for m in MENSAGENS if m["id"] == "pergunta_causa")
    assert "pedidos-api" in item["mensagem"]


# --- ponta a ponta: sessão A confirma, sessão B pergunta ----------------------------------------


def _resolvedor():
    """Atualiza o episódio ativo parecido quando existe um; senão o resolvedor nem é chamado."""

    def decide(entrada):
        antigo = re.search(r"ID: (\S+) \| Incidente: (\S+)", entrada["existentes"])
        return ResolucaoMemoria(
            acao="atualizar_existente", id_memoria_antiga=antigo.group(1), motivo="mesmo incidente"
        )

    return RunnableLambda(decide)


def _registro_falso(ferramentas):
    """Agente de registro sem modelo: chama gravar_episodio com a mensagem como causa."""
    gravar = next(f for f in ferramentas if f.name == "gravar_episodio")

    def registrar(estado, config):
        gravar.invoke(
            {"resumo": "sintoma", "causa": estado["mensagem"], "levantada_pelo_agente": False},
            config=config,
        )
        return "Registrei."

    return RunnableLambda(registrar)


def _fabrica_conversa(memoria):
    esperadas = {
        turno["mensagem"]: turno["intencao_esperada"]
        for conversa in CONVERSAS
        for turno in conversa["turnos"]
    }

    def fabrica(cenario):
        fonte = FonteLoja.gravada("cenario_teste", raiz=RAIZ)
        ferramentas = montar_ferramentas(fonte, memoria=memoria, resolver=_resolvedor())
        modelo = roteiro(
            chamada("consultar_memoria", {"servico": "pedidos-api", "descricao": "x"}), JSON_OK
        )
        pipeline = montar_pipeline(
            None,
            _moderar,
            nlu=RunnableLambda(
                lambda e: AnaliseNLU(intencao=esperadas[e["mensagem"]], servico="pedidos-api")
            ),
            investigacao=montar_investigador(modelo, ferramentas),
            memoria=memoria,
            registro=_registro_falso(ferramentas),
        )
        return montar_conversa(pipeline, roteiro("RESUMO"))

    return fabrica


def test_sessao_a_confirma_e_sessao_b_consulta_o_episodio():
    memoria = MemoriaLongoPrazo(DeterministicFakeEmbedding(size=64), agora=lambda: AGORA)
    fabrica = _fabrica_conversa(memoria)
    por_id = {conversa["id"]: conversa for conversa in CONVERSAS}
    a = rodar_conversa_sessao(fabrica, por_id["confirmacao_e_recorrencia"])
    b = rodar_conversa_sessao(fabrica, por_id["recorrencia_sessao_b"])
    assert [r.rota for r in a] == ["investigacao", "investigacao", "memoria"]
    assert a[-1].episodio is not None and memoria.consultar_episodios("pedidos-api", "deploy")
    assert a[-1].resolucao is not None
    assert [r.rota for r in b] == ["investigacao", "investigacao"]
    linhas = linhas_bateria(_turnos(por_id["recorrencia_sessao_b"]), b)
    assert [linha["memória consultada"] for linha in linhas] == ["sim", "sim"]
    linhas_a = linhas_bateria(_turnos(por_id["confirmacao_e_recorrencia"]), a)
    assert linhas_a[-1]["memória registrada"] == "registrado" and linhas_a[-1]["ok"]


def test_troca_de_causa_aparece_como_atualizado_e_arquiva_a_anterior():
    memoria = MemoriaLongoPrazo(DeterministicFakeEmbedding(size=64), agora=lambda: AGORA)
    conversa = next(c for c in CONVERSAS if c["id"] == "troca_de_causa")
    respostas = rodar_conversa_sessao(_fabrica_conversa(memoria), conversa)
    linhas = linhas_bateria(_turnos(conversa), respostas)
    assert [linha["memória registrada"] for linha in linhas] == ["-", "registrado", "atualizado"]
    assert respostas[-1].episodio_anterior.status == "arquivado"
    assert {e.status for e in memoria.listar_episodios("pedidos-api")} == {"ativo", "arquivado"}


def test_mensagem_de_hipotese_com_pedido_de_gravar_nao_grava_e_acerta_a_rota():
    memoria = MemoriaLongoPrazo(DeterministicFakeEmbedding(size=64), agora=lambda: AGORA)
    ferramentas = montar_ferramentas(
        FonteLoja.gravada("cenario_teste", raiz=RAIZ), memoria=memoria, resolver=_resolvedor()
    )
    item = next(m for m in MENSAGENS if m["id"] == "hipotese_pede_gravar")
    argumentos = {"resumo": "r", "causa": "pool baixo", "levantada_pelo_agente": False}
    pipeline = montar_pipeline(
        None,
        _moderar,
        nlu=RunnableLambda(lambda e: AnaliseNLU(intencao="investigar_erro", servico="pedidos-api")),
        investigacao=montar_investigador(
            roteiro(chamada("gravar_episodio", argumentos), JSON_OK), ferramentas
        ),
        memoria=memoria,
        registro=_registro_falso(ferramentas),
    )
    resposta = rodar_bateria(pipeline, [item])[0]
    assert resposta.rota == "investigacao" and resposta.episodio is None
    assert memoria.listar_episodios("pedidos-api") == []
    assert linhas_bateria([item], [resposta])[0]["ok"]
