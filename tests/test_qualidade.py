"""Travas determinísticas de qualidade da resposta: dado faltante indevido e ação que só repete
uma consulta que as ferramentas já fizeram."""

from agente.qualidade import (
    acao_de_consulta,
    dado_faltante_valido,
    repete_consulta,
    sanear_analise,
    sanear_nlu,
)
from agente.schemas import AcaoSugerida, AnaliseIncidente, AnaliseNLU, Hipotese

PERGUNTA = "O pagamentos-api está com erros desde as 14h. Qual a causa provável?"
FERRAMENTAS = {"buscar_logs", "buscar_metricas", "listar_deploys", "consultar_wiki", "sugerir_acao"}


def test_dado_faltante_que_e_a_propria_causa_e_descartado():
    assert not dado_faltante_valido("causa provável dos erros", PERGUNTA)
    assert not dado_faltante_valido("o motivo dos erros 500", PERGUNTA)
    assert not dado_faltante_valido("raiz do problema", PERGUNTA)


def test_dado_faltante_que_as_ferramentas_alcancam_e_descartado():
    assert not dado_faltante_valido("logs do pagamentos-api no período", PERGUNTA)
    assert not dado_faltante_valido("métricas de requisições", PERGUNTA)
    assert not dado_faltante_valido("deploys recentes", PERGUNTA)
    assert not dado_faltante_valido("análise do volume de requisições", PERGUNTA)
    assert not dado_faltante_valido("qual o estado atual do banco de dados", "e o banco?")


def test_dado_faltante_que_repete_a_pergunta_e_descartado():
    pergunta = "Qual a categoria mais comum dos incidentes do pedidos-api?"
    assert not dado_faltante_valido("categoria mais comum dos incidentes", pergunta)


def test_dado_faltante_que_so_o_engenheiro_sabe_fica():
    assert dado_faltante_valido("nome do serviço afetado", "está tudo dando erro")
    assert dado_faltante_valido("horário em que o erro começou", "o checkout quebrou")
    assert dado_faltante_valido("limite contratado com o provedor de SMS", PERGUNTA)


def test_sanear_nlu_remove_so_o_dado_indevido():
    nlu = AnaliseNLU(
        intencao="investigar_erro",
        servico="pagamentos-api",
        dado_faltante="causa provável dos erros",
    )
    limpo = sanear_nlu(nlu, PERGUNTA)
    assert limpo.dado_faltante is None and limpo.servico == "pagamentos-api"
    # "qual serviço" sai: o Investigador descobre o serviço pela visão geral
    sem_servico = AnaliseNLU(intencao="investigar_erro", dado_faltante="nome do serviço afetado")
    assert sanear_nlu(sem_servico, "deu erro").dado_faltante is None
    bom = AnaliseNLU(intencao="investigar_erro", dado_faltante="horário em que o erro começou")
    assert sanear_nlu(bom, "deu erro").dado_faltante == "horário em que o erro começou"
    assert sanear_nlu(None, PERGUNTA) is None


def test_acao_de_consulta_reconhece_verificar_e_consultar():
    assert acao_de_consulta("Verifique os logs para identificar o volume de requisições")
    assert acao_de_consulta("Consulte o limite documentado do plano contratado com o PagaFácil")
    assert acao_de_consulta("Checar as métricas de CPU")
    assert acao_de_consulta("Analisar os deploys recentes")
    assert not acao_de_consulta("Respeitar o Retry-After de 30 s com backoff exponencial")
    assert not acao_de_consulta("Limitar as chamadas ao PagaFácil a menos de 100 por minuto")
    assert not acao_de_consulta("Reverter o deploy v3.2.1")


def test_repete_consulta_so_quando_a_ferramenta_ja_rodou():
    assert repete_consulta("Verifique os logs do pagamentos-api", FERRAMENTAS)
    assert repete_consulta("Consulte o limite documentado do PagaFácil", FERRAMENTAS)
    assert not repete_consulta(
        "Conferir o diff da v3.2.1", FERRAMENTAS
    )  # comparar_versoes não rodou
    assert repete_consulta("Conferir o diff da v3.2.1", FERRAMENTAS | {"comparar_versoes"})
    assert not repete_consulta("Enfileirar os pagamentos no modo degradado", FERRAMENTAS)


def _analise(passos, acoes):
    return AnaliseIncidente(
        severidade="alta",
        categoria="dependencia_externa",
        resumo="429 do PagaFácil.",
        hipoteses=[
            Hipotese(
                causa="limite de 100/min excedido",
                confianca=0.9,
                evidencia="429 (x150), Retry-After: 30",
            ),
            Hipotese(causa="falha no provedor", confianca=0.1, evidencia="sem 503"),
        ],
        proximos_passos=passos,
        acoes_sugeridas=acoes,
    )


def test_sanear_analise_tira_passos_e_acoes_que_repetem_consulta():
    acoes = [
        AcaoSugerida(acao="Verifique os logs para identificar o volume", motivo="m", risco="baixo"),
        AcaoSugerida(acao="Respeitar o Retry-After de 30 s", motivo="m", risco="baixo"),
    ]
    analise = _analise(
        [
            "Verifique os logs para identificar o volume de requisições.",
            "Ativar o modo degradado para enfileirar pagamentos.",
        ],
        acoes,
    )
    limpa = sanear_analise(analise, FERRAMENTAS)
    assert limpa.proximos_passos == ["Ativar o modo degradado para enfileirar pagamentos."]
    assert [a.acao for a in limpa.acoes_sugeridas] == ["Respeitar o Retry-After de 30 s"]


def test_sanear_analise_sem_passo_util_usa_as_acoes_sugeridas():
    acoes = [AcaoSugerida(acao="Respeitar o Retry-After de 30 s", motivo="m", risco="baixo")]
    analise = _analise(["Verifique os logs.", "Consulte a wiki do PagaFácil."], acoes)
    limpa = sanear_analise(analise, FERRAMENTAS)
    assert limpa.proximos_passos == [
        "Avaliar e aprovar a ação sugerida: Respeitar o Retry-After de 30 s"
    ]


def test_sanear_analise_sem_nada_util_parte_da_causa_principal():
    analise = _analise(["Verifique os logs."], [])
    passos = sanear_analise(analise, FERRAMENTAS).proximos_passos
    assert passos == ["Corrigir a causa principal: limite de 100/min excedido"]


def test_passos_genericos_de_monitorar_ou_investigar_o_que_ja_foi_lido():
    passos = [
        "monitorar a carga de requisições e a taxa de erros para identificar padrões",
        "investigar a infraestrutura e dependências externas para possíveis falhas",
    ]
    assert all(repete_consulta(p, FERRAMENTAS) for p in passos)
    assert not repete_consulta("monitorar a conclusão do REINDEX da tabela estoque", FERRAMENTAS)


# --- qualidade das ações: desfazer a causa primeiro, sem condicional, com dado da evidência ---

from agente.qualidade import acao_condicional, dados_da_evidencia, ordenar_e_filtrar_acoes  # noqa: E402

EVIDENCIA_POOL = (
    "comparar_versoes: config/db.yaml troca pool_max de 20 para 10 na v3.2.0; "
    "buscar_logs: 'timeout aguardando conexão livre do pool' (x284)"
)
CAUSA_POOL = "a v3.2.0 reduziu o pool_max de 20 para 10 e esgotou as conexões"


def _a(acao, motivo, risco="medio"):
    return AcaoSugerida(acao=acao, motivo=motivo, risco=risco)


def test_dados_da_evidencia_pega_valores_versoes_e_chaves():
    dados = dados_da_evidencia(EVIDENCIA_POOL)
    assert {"20", "10", "284", "v3.2.0", "pool_max"} <= dados


def test_acao_condicional():
    assert acao_condicional(_a("Escalar horizontalmente", "se o pico de tráfego for legítimo"))
    assert acao_condicional(_a("Aumentar réplicas, se necessário", "m"))
    assert acao_condicional(_a("Caso persista, abrir chamado", "m"))
    assert not acao_condicional(_a("Restaurar pool_max para 20", "o diff mudou de 20 para 10"))


def test_acoes_do_pool_restauram_o_valor_anterior_primeiro_e_tiram_as_fracas():
    acoes = [
        _a("Aumentar o pool para 15", "sem exceder o limite anterior", "baixo"),
        _a("Reduzir o tempo máximo das consultas para 2000ms", "consultas lentas", "baixo"),
        _a("Escalar horizontalmente", "se o pico de tráfego for legítimo", "alto"),
        _a("Fazer rollback da v3.2.0", "o diff da v3.2.0 cortou pool_max de 20 para 10", "medio"),
    ]
    finais = ordenar_e_filtrar_acoes(acoes, CAUSA_POOL, EVIDENCIA_POOL)
    assert [a.acao for a in finais] == ["Fazer rollback da v3.2.0"]


def test_sem_acao_de_desfazer_o_codigo_inclui_restaurar_o_valor_anterior():
    acoes = [_a("Aumentar o pool para 15", "o pool_max caiu para 10", "baixo")]
    finais = ordenar_e_filtrar_acoes(acoes, CAUSA_POOL, EVIDENCIA_POOL)
    assert finais[0].acao == "Restaurar pool_max para 20 (valor anterior à v3.2.0)"
    assert "20 para 10" in finais[0].motivo and finais[0].risco == "baixo"
    assert finais[0].status == "sugerida (não executada)"


def test_causa_externa_ordena_por_risco_e_nao_inventa_rollback():
    evidencia = "buscar_logs: 150 respostas 429 (X-RateLimit-Limit: 100/min, Retry-After: 30)"
    causa = "limite de 100/min do PagaFácil excedido"
    acoes = [
        _a("Pedir ao provedor aumento de cota", "150 respostas 429 acima de 100/min", "alto"),
        _a("Respeitar o Retry-After com backoff", "Retry-After: 30 nos logs", "baixo"),
        _a("Colocar as chamadas em fila", "volume acima de 100/min", "medio"),
    ]
    finais = ordenar_e_filtrar_acoes(acoes, causa, evidencia)
    assert [a.risco for a in finais] == ["baixo", "medio", "alto"]
    assert not any("rollback" in a.acao.lower() or "restaurar" in a.acao.lower() for a in finais)


def test_risco_alto_sem_dado_da_evidencia_sai():
    acoes = [_a("Migrar o banco para outro cluster", "melhora a performance", "alto")]
    assert ordenar_e_filtrar_acoes(acoes, "REINDEX em andamento", "REINDEX TABLE estoque") == []


def test_sem_dados_na_evidencia_so_tira_condicionais():
    acoes = [_a("Reiniciar o worker", "libera memória", "baixo"), _a("Escalar", "se necessário")]
    finais = ordenar_e_filtrar_acoes(acoes, "falha", "")
    assert [a.acao for a in finais] == ["Reiniciar o worker"]


def test_acoes_quase_iguais_ficam_so_a_mais_especifica():
    acoes = [
        _a("Fazer rollback para a versão anterior", "a v2.14.0 trouxe o erro", "baixo"),
        _a("Fazer rollback para a versão v2.13.0", "a v2.14.0 trouxe o erro", "baixo"),
        _a("Reagendar o REINDEX para a janela de manutenção", "REINDEX bloqueia", "baixo"),
        _a("Reagendar o REINDEX para a janela de manutenção, entre 02h e 04h", "REINDEX", "medio"),
    ]
    evidencia = "listar_deploys: v2.14.0; REINDEX TABLE estoque"
    finais = ordenar_e_filtrar_acoes(acoes, "a v2.14.0 quebrou o cupom", evidencia)
    textos = [a.acao for a in finais]
    assert "Fazer rollback para a versão v2.13.0" in textos
    assert "Fazer rollback para a versão anterior" not in textos
    assert sum("Reagendar o REINDEX" in t for t in textos) == 1


def test_sem_nenhuma_acao_com_dado_fica_a_de_menor_risco_sem_condicional():
    acoes = [
        _a("Renovar o certificado do provedor de JWKS", "o certificado expirou", "baixo"),
        _a("Trocar de provedor", "outro provedor é mais estável", "alto"),
        _a("Escalar, se necessário", "m", "baixo"),
    ]
    finais = ordenar_e_filtrar_acoes(
        acoes, "certificado expirou", "x509: certificate has expired (x55)"
    )
    assert [a.acao for a in finais] == ["Renovar o certificado do provedor de JWKS"]


# --- dado que falta da hipótese: nunca pedir ao engenheiro o que as ferramentas alcançam ---


def test_dado_que_pede_logs_metricas_ou_uso_de_recurso_e_descartado():
    for dado in (
        "logs ou métricas que confirmem o uso do disco",
        "uso de disco do servidor",
        "confirmar o consumo de memória do container",
        "verificar a CPU no horário",
    ):
        assert not dado_faltante_valido(dado, "o disco encheu"), dado


def test_sanear_analise_transforma_dado_indevido_da_hipotese_em_lacuna():
    from agente.qualidade import PREFIXO_LACUNA

    analise = AnaliseIncidente(
        severidade="alta",
        categoria="disco_cheio",
        resumo="r",
        hipoteses=[
            Hipotese(
                causa="disco cheio",
                confianca=0.4,
                evidencia_insuficiente=True,
                dado_que_falta="logs ou métricas que confirmem o uso do disco",
            ),
            Hipotese(
                causa="limite do provedor",
                confianca=0.2,
                evidencia_insuficiente=True,
                dado_que_falta="limite contratado com o provedor de SMS",
            ),
        ],
        proximos_passos=["Liberar espaço em /tmp"],
    )
    limpa = sanear_analise(analise, {"buscar_logs", "buscar_metricas"})
    assert limpa.hipoteses[0].dado_que_falta.startswith(PREFIXO_LACUNA)
    assert "uso do disco" in limpa.hipoteses[0].dado_que_falta
    assert limpa.hipoteses[1].dado_que_falta == "limite contratado com o provedor de SMS"


def test_acao_que_inventa_outro_valor_para_a_chave_do_diff_sai():
    acoes = [
        _a("Restaurar o pool_max para 20", "o diff cortou de 20 para 10", "baixo"),
        _a("Aumentar o pool de conexões para 15", "o pool_max caiu para 10", "medio"),
    ]
    finais = ordenar_e_filtrar_acoes(acoes, CAUSA_POOL, EVIDENCIA_POOL)
    assert [a.acao for a in finais] == ["Restaurar o pool_max para 20"]


def test_acoes_com_o_mesmo_verbo_e_metade_dos_termos_sao_repetidas():
    acoes = [
        _a("Renovar o certificado e recarregar o serviço", "certificado expirou (x55)", "medio"),
        _a("Renovar o certificado SSL do provedor de JWKS", "certificado expirou (x55)", "medio"),
    ]
    finais = ordenar_e_filtrar_acoes(acoes, "certificado expirou", "x509 expirado (x55)")
    assert len(finais) == 1
