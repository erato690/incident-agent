from agente.registro import Registro, RegistroTurno
from agente.schemas import (
    AnaliseIncidente,
    Hipotese,
    PassoTrajetoria,
    RespostaFixa,
    RespostaTurno,
    ResultadoModeracao,
)

MOD = ResultadoModeracao(status="ok")


def _analise() -> AnaliseIncidente:
    return AnaliseIncidente(
        severidade="alta",
        categoria="banco",
        servico="pedidos-api",
        resumo="Timeouts no checkout.",
        hipoteses=[
            Hipotese(causa="Pool esgotado", confianca=0.9, evidencia="pool_max=10"),
            Hipotese(causa="Deploy", confianca=0.3, evidencia="v3.2.0"),
        ],
        proximos_passos=["Subir o pool"],
    )


def _investigacao(**extra) -> RespostaTurno:
    passo = PassoTrajetoria(ferramenta="buscar_logs", duracao_ms=5, tamanho=10)
    return RespostaTurno(
        rota="investigacao", moderacao=MOD, analise=_analise(), trajetoria=[passo], **extra
    )


def test_de_resposta_investigacao_resume_e_mascara_pergunta():
    r = RegistroTurno.de_resposta(
        "s1", "falhou com senha=abc123", _investigacao(), 120, incidente_id="inc-1", cenario="x"
    )
    assert "abc123" not in r.pergunta
    assert "Timeouts no checkout." in r.resposta and "Pool esgotado" in r.resposta
    assert r.rota == "investigacao" and r.ferramentas == ["buscar_logs"]
    assert r.incidente_id == "inc-1" and r.cenario == "x" and r.duracao_ms == 120
    assert r.auditoria_aprovada is None and r.motivos_auditoria == [] and r.aviso is None


def test_de_resposta_fixa_e_erro():
    fixa = RespostaTurno(
        rota="fixa", moderacao=MOD, fixa=RespostaFixa(texto="Olá!", camada=1, categoria="saudacao")
    )
    assert RegistroTurno.de_resposta("s", "oi", fixa, 1).resposta == "Olá!"
    erro = RespostaTurno(rota="erro", moderacao=MOD, erro="falhou")
    assert RegistroTurno.de_resposta("s", "oi", erro, 1).resposta == "falhou"


def test_de_resposta_le_auditoria_e_aviso_opcionais():
    class Aud:
        aprovada = False
        motivos = ["número inventado"]

    resposta = _investigacao()
    # campos futuros ainda podem não existir no schema: simula via getattr
    objeto = type("R", (), {})()
    for campo in ("rota", "analise", "trajetoria", "fixa", "erro", "nlu"):
        setattr(objeto, campo, getattr(resposta, campo))
    objeto.auditoria, objeto.aviso = Aud(), "Resposta reprovada"
    r = RegistroTurno.de_resposta("s", "q", objeto, 1)
    assert r.auditoria_aprovada is False and r.motivos_auditoria == ["número inventado"]
    assert r.aviso == "Resposta reprovada"


def test_registro_adicionar_listar_salvar_carregar(tmp_path):
    reg = Registro()
    reg.adicionar(RegistroTurno.de_resposta("a", "p1", _investigacao(), 1))
    reg.adicionar(RegistroTurno.de_resposta("b", "p2", _investigacao(), 2))
    assert len(reg.listar()) == 2
    assert [t.pergunta for t in reg.listar("b")] == ["p2"]
    arquivo = tmp_path / "sub" / "reg.json"
    reg.salvar(arquivo)
    novo = Registro.carregar(arquivo)
    assert novo.listar() == reg.listar()
    assert Registro.carregar(tmp_path / "nao_existe.json").listar() == []
