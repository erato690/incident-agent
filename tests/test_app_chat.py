"""Funções puras de apoio à API do chat (sem chave)."""

from agente.schemas import (
    AnaliseIncidente,
    AnaliseNLU,
    Auditoria,
    Hipotese,
    PassoTrajetoria,
    RespostaTurno,
)
from app.formatacao import (
    dados_faltantes,
    fontes_consultadas,
    mensagem_erro,
    rotulo_ferramenta,
)


def _resposta(**campos) -> RespostaTurno:
    return RespostaTurno.model_validate(
        {"rota": "investigacao", "moderacao": {"status": "ok"}, **campos}
    )


def _analise(falta: str | None = None) -> AnaliseIncidente:
    return AnaliseIncidente(
        severidade="critica",
        categoria="banco",
        resumo="r",
        hipoteses=[
            Hipotese(causa="a", confianca=0.8, evidencia="e"),
            Hipotese(
                causa="b",
                confianca=0.2,
                evidencia=None if falta else "e2",
                evidencia_insuficiente=falta is not None,
                dado_que_falta=falta,
            ),
        ],
        proximos_passos=["p"],
    )


def test_dados_faltantes_so_do_nlu_e_da_principal():
    nlu = AnaliseNLU.model_construct(dado_faltante="Nome do serviço afetado")
    resposta = _resposta(analise=_analise("métricas do pool"))
    resposta.nlu = nlu
    # o dado da hipótese secundária não vira pergunta; o do NLU sim
    assert dados_faltantes(resposta) == ["Nome do serviço afetado"]
    assert dados_faltantes(_resposta(analise=_analise("métricas do pool"))) == []


def test_fontes_e_passos():
    passos = [
        PassoTrajetoria(ferramenta="buscar_logs", duracao_ms=5, tamanho=1),
        PassoTrajetoria(ferramenta="buscar_logs", duracao_ms=6, tamanho=1, reserva=True),
        PassoTrajetoria(ferramenta="x", duracao_ms=1, tamanho=1, erro="falhou"),
    ]
    assert fontes_consultadas(_resposta(trajetoria=passos)) == ["logs da loja", "x"]
    assert rotulo_ferramenta("consultar_sql") == "histórico de incidentes (SQL)"


def test_mensagem_erro_so_primeira_linha():
    texto = mensagem_erro(RuntimeError("timeout\nlinha 2"))
    assert "RuntimeError: timeout" in texto and "linha 2" not in texto


def test_selo_do_texto_copiado_traz_o_veredito():
    from app.formatacao import selo_auditoria

    resposta = _resposta(auditoria=Auditoria(aprovada=False, veredito="refuta"))
    assert selo_auditoria(resposta) == "auditada: reprovada (veredito: refuta)"


def _analise_com_dado(dado, insuficiente=True):
    return AnaliseIncidente(
        severidade="alta",
        categoria="c",
        resumo="r",
        hipoteses=[
            Hipotese(
                causa="a",
                confianca=0.5,
                evidencia=None if insuficiente else "e",
                evidencia_insuficiente=insuficiente,
                dado_que_falta=dado,
            ),
            Hipotese(causa="b", confianca=0.1, evidencia="e2"),
        ],
        proximos_passos=["p"],
    )


def test_perguntas_separam_dado_de_fato_da_wiki_e_lacunas():
    from app.formatacao import lacunas, perguntas

    wiki = PassoTrajetoria(
        ferramenta="consultar_wiki",
        duracao_ms=1,
        tamanho=1,
        observacao="NÃO ENCONTRADO: pergunte ao engenheiro o limite do provedor de SMS",
    )
    resposta = _resposta(
        analise=_analise_com_dado("limite contratado com o provedor de SMS"), trajetoria=[wiki]
    )
    assert perguntas(resposta) == [
        {"texto": "limite contratado com o provedor de SMS", "tipo": "fato"}
    ]
    nlu = _resposta(analise=_analise_com_dado(None, insuficiente=False))
    nlu.nlu = AnaliseNLU.model_construct(dado_faltante="qual serviço foi afetado")
    assert perguntas(nlu) == [{"texto": "qual serviço foi afetado", "tipo": "dado"}]
    lacuna = _resposta(analise=_analise_com_dado("Lacuna: uso do disco (nenhuma ferramenta traz)"))
    assert perguntas(lacuna) == [] and lacunas(lacuna) == ["uso do disco (nenhuma ferramenta traz)"]


def test_causa_a_confirmar_so_no_pedido_de_post_mortem_sem_confirmacao():
    from agente.integrado import CATEGORIA_SEM_CONFIRMACAO, TEXTO_SEM_CONFIRMACAO
    from agente.schemas import RespostaFixa
    from app.formatacao import causa_a_confirmar

    texto = TEXTO_SEM_CONFIRMACAO.format(
        causa="pool_max de 20 para 10", confianca=0.9, evidencia="e"
    )
    pedido = _resposta(
        rota="fixa", fixa=RespostaFixa(texto=texto, camada=2, categoria=CATEGORIA_SEM_CONFIRMACAO)
    )
    assert causa_a_confirmar(pedido) == "pool_max de 20 para 10"
    outra = _resposta(rota="fixa", fixa=RespostaFixa(texto="Olá", camada=1, categoria="saudacao"))
    assert causa_a_confirmar(outra) is None
