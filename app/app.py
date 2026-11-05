"""Interface Streamlit: aba de uso (conversa) e aba de análise (registro dos turnos)."""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

from app.formatacao import (  # noqa: E402
    AVISO_RODAPE,
    cenarios_disponiveis,
    linhas_registro,
    markdown_resposta,
)

PASTA_CENARIOS = RAIZ / "dados_dummy" / "cenarios"


@st.cache_resource(show_spinner="Montando o agente...")
def obter_agente():
    from agente.integrado import montar_agente_integrado

    from agente.config import escolher_llm

    return montar_agente_integrado(escolher_llm())


def _exigir_chave() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("DEEPSEEK_API_KEY"):
        st.warning(
            "Chave de API não encontrada. Configure OPENAI_API_KEY (no `.env` local ou nas "
            "variáveis de ambiente do Railway) e reinicie o app."
        )
        st.stop()


def _trajetoria(passos) -> None:
    with st.expander(f"Trajetória ({len(passos)} chamadas de ferramenta)"):
        for passo in passos:
            st.markdown(f"`{passo.ferramenta}` ({passo.duracao_ms} ms)")
            st.json(passo.argumentos, expanded=False)


def _nova_sessao(agente, cenario_id: str) -> None:
    st.session_state.sessao = agente.abrir_sessao(cenario_id)
    st.session_state.mensagens = []


def _aba_uso(agente) -> None:
    cenarios = cenarios_disponiveis(PASTA_CENARIOS)
    rotulos = {f"{c['titulo']} ({c['id']})": c["id"] for c in cenarios}
    escolhido = st.selectbox("Cenário", list(rotulos))
    if st.button("Nova sessão") or "sessao" not in st.session_state:
        _nova_sessao(agente, rotulos[escolhido])
    for msg in st.session_state.mensagens:
        with st.chat_message(msg["papel"]):
            st.markdown(msg["texto"])
            if msg.get("trajetoria"):
                _trajetoria(msg["trajetoria"])
    pergunta = st.chat_input("Descreva o incidente ou faça uma pergunta")
    if pergunta:
        _responder(agente, pergunta)


def _responder(agente, pergunta: str) -> None:
    st.session_state.mensagens.append({"papel": "user", "texto": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.chat_message("assistant"), st.spinner("Investigando..."):
        resposta = agente.turno(st.session_state.sessao, pergunta)
        st.markdown(markdown_resposta(resposta))
        _trajetoria(resposta.trajetoria)
    st.session_state.mensagens.append(
        {
            "papel": "assistant",
            "texto": markdown_resposta(resposta),
            "trajetoria": resposta.trajetoria,
        }
    )
    st.session_state.ultima_resposta = resposta


def _detalhe_turno(turno) -> None:
    st.markdown(f"**Pergunta:** {turno.pergunta}")
    st.markdown(f"**Resposta:** {turno.resposta}")
    if turno.aviso:
        st.warning(turno.aviso)
    for motivo in turno.motivos_auditoria:
        st.markdown(f"- Auditor: {motivo}")
    _trajetoria(turno.trajetoria)


def _aba_analise(agente) -> None:
    registros = agente.registro.listar()
    if not registros:
        st.info("Nenhum turno registrado ainda. Use a aba Uso.")
        return
    st.dataframe(linhas_registro(registros), use_container_width=True)
    indice = st.selectbox(
        "Turno",
        range(len(registros)),
        format_func=lambda i: f"{i + 1}. {registros[i].pergunta[:60]}",
    )
    _detalhe_turno(registros[indice])


def main() -> None:
    st.set_page_config(page_title="Agente de incidentes", layout="wide")
    st.title("Agente de análise de incidentes")
    _exigir_chave()
    agente = obter_agente()
    uso, analise = st.tabs(["Uso", "Análise"])
    with uso:
        _aba_uso(agente)
    with analise:
        _aba_analise(agente)
    st.caption(AVISO_RODAPE)


main()
