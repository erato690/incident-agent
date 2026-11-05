"""Testes da interface: formatação pura (sem Streamlit nem chave) e compilação do app."""

import json
import py_compile
from pathlib import Path

from agente.registro import RegistroTurno
from agente.schemas import (
    AcaoSugerida,
    AnaliseIncidente,
    Auditoria,
    Hipotese,
    PassoTrajetoria,
    RespostaFixa,
    RespostaTurno,
)
from app.formatacao import cenarios_disponiveis, linhas_registro, markdown_resposta

RAIZ = Path(__file__).resolve().parent.parent


def _analise() -> AnaliseIncidente:
    return AnaliseIncidente(
        severidade="alta",
        categoria="banco",
        resumo="Timeouts no pedidos-api.",
        hipoteses=[
            Hipotese(causa="Deploy v3.2.1", confianca=0.8, evidencia="deploy às 15:40"),
            Hipotese(causa="Pool esgotado", confianca=0.3, evidencia="pool=0"),
        ],
        proximos_passos=["Verificar deploy"],
        acoes_sugeridas=[
            AcaoSugerida(acao="Reverter o deploy", motivo="Coincide com o início", risco="medio")
        ],
    )


def _resposta(**campos) -> RespostaTurno:
    base = {"rota": "investigacao", "moderacao": {"status": "ok"}}
    return RespostaTurno.model_validate({**base, **campos})


def test_markdown_analise_aprovada():
    texto = markdown_resposta(_resposta(analise=_analise(), auditoria=Auditoria(aprovada=True)))
    assert "alta" in texto and "Deploy v3.2.1" in texto and "80%" in texto
    assert "deploy às 15:40" in texto
    assert "Reverter o deploy (sugerida, não executada)" in texto
    assert "auditada: aprovada" in texto


def test_markdown_aviso_e_reprovada():
    texto = markdown_resposta(
        _resposta(
            analise=_analise(),
            aviso="Hora divergente",
            auditoria=Auditoria(aprovada=False, motivos=["hora"]),
        )
    )
    assert texto.startswith("> **ATENÇÃO:** Hora divergente")
    assert "auditada: reprovada" in texto


def test_markdown_fixa_e_erro():
    fixa = markdown_resposta(
        _resposta(rota="fixa", fixa=RespostaFixa(texto="Olá!", camada=1, categoria="saudacao"))
    )
    assert "Olá!" in fixa and "não auditada" in fixa
    erro = markdown_resposta(_resposta(rota="erro", erro="falhou"))
    assert "**Erro:** falhou" in erro


def test_linhas_registro():
    reg = RegistroTurno(
        session_id="abcdef123456",
        pergunta="p",
        rota="investigacao",
        resposta="r",
        ferramentas=["buscar_logs", "consultar_banco"],
        auditoria_aprovada=False,
        duracao_ms=1200,
        trajetoria=[PassoTrajetoria(ferramenta="buscar_logs", duracao_ms=5, tamanho=10)],
    )
    linha = linhas_registro([reg])[0]
    assert linha["sessão"] == "abcdef12"
    assert linha["ferramentas"] == "buscar_logs, consultar_banco"
    assert linha["auditoria"] == "reprovada" and linha["duração (ms)"] == 1200
    assert len(linha["hora"]) == 8


def test_cenarios_disponiveis(tmp_path):
    (tmp_path / "a.json").write_text(
        json.dumps({"cenario": {"id": "a", "titulo": "Zeta", "servico": "s"}}), encoding="utf-8"
    )
    (tmp_path / "b.json").write_text(
        json.dumps({"cenario": {"id": "b", "titulo": "Alfa", "servico": "s"}}), encoding="utf-8"
    )
    assert [c["id"] for c in cenarios_disponiveis(tmp_path)] == ["b", "a"]


def test_cenarios_reais():
    ids = {c["id"] for c in cenarios_disponiveis(RAIZ / "dados_dummy" / "cenarios")}
    assert "banco_lento_com_deploy" in ids


def test_app_compila():
    py_compile.compile(str(RAIZ / "app" / "app.py"), doraise=True)


def test_app_sem_chave_mostra_aviso(monkeypatch):
    from streamlit.testing.v1 import AppTest

    for var in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.setenv(var, "")
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    app = AppTest.from_file(str(RAIZ / "app" / "app.py"), default_timeout=20).run()
    assert not app.exception
    assert "OPENAI_API_KEY" in app.warning[0].value
