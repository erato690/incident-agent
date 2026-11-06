"""Interface Streamlit: aba de uso (chat por incidente) e aba de análise (registro dos turnos).

Só desenha: a lógica do agente fica em `agente/`, e a formatação pura em `app/formatacao.py`."""

import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

from app.formatacao import (  # noqa: E402
    AVISO_RODAPE,
    cenarios_disponiveis,
    dados_faltantes,
    fontes_consultadas,
    linhas_passos,
    linhas_registro,
    mensagem_erro,
    rotulo_ferramenta,
    selo,
    selo_auditor,
    selo_risco,
    selo_severidade,
    sugestoes_iniciais,
)

PASTA_CENARIOS = RAIZ / "dados_dummy" / "cenarios"

# CSS mínimo: o tema vem de .streamlit/config.toml. Aqui só o que o tema não cobre:
# mensagem do engenheiro à direita, foco visível no teclado e respeito a movimento reduzido.
CSS = """
<style>
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  flex-direction: row-reverse;
  margin-left: 12%;
  background: #1E293B;
  border: 1px solid #334155;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
  [data-testid="stChatMessageContent"] { text-align: left; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
  margin-right: 4%;
}
:focus-visible { outline: 2px solid #4ADE80 !important; outline-offset: 2px; }
button { cursor: pointer; }
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
</style>
"""


@st.cache_resource(show_spinner="Montando o agente...")
def obter_agente():
    from agente.config import escolher_llm
    from agente.integrado import montar_agente_integrado

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


def _seg(segundos: float) -> str:
    return f"{segundos:.1f} s".replace(".", ",")


# --- Sessão ---


def _nova_sessao(agente, cenario: dict) -> None:
    st.session_state.sessao = agente.abrir_sessao(cenario["id"])
    st.session_state.cenario = cenario
    st.session_state.mensagens = []
    st.session_state.pop("pendente", None)


def _barra_lateral(agente) -> None:
    cenarios = cenarios_disponiveis(PASTA_CENARIOS)
    with st.sidebar:
        st.subheader("Incidente")
        escolhido = st.selectbox(
            "Cenário da loja",
            cenarios,
            format_func=lambda c: c["titulo"],
            help="Cada cenário simula um incidente diferente na loja de testes.",
        )
        trocou = st.session_state.get("cenario", {}).get("id") != escolhido["id"]
        if "sessao" not in st.session_state or trocou:
            _nova_sessao(agente, escolhido)
        if st.button("Nova sessão", icon=":material/add:", width="stretch"):
            _nova_sessao(agente, escolhido)
            st.rerun()
        servico = escolhido.get("servico") or "não informado"
        st.caption(f"Serviço: `{servico}`")
        st.caption(f"Sessão: `{st.session_state.sessao.session_id[:8]}`")
        st.divider()
        st.caption(AVISO_RODAPE)


# --- Resposta do agente ---


def _bloco_hipoteses(analise) -> None:
    principal, *outras = analise.hipoteses
    st.markdown("**Causa provável**")
    st.markdown(f"{principal.causa} · confiança {principal.confianca:.0%}")
    if principal.evidencia:
        st.markdown(f"> **Evidência:** {principal.evidencia}")
    else:
        st.caption("Sem evidência direta nos dados consultados.")
    if outras:
        with st.expander(f"Outras hipóteses ({len(outras)})"):
            for h in outras:
                st.markdown(f"- **{h.causa}** · confiança {h.confianca:.0%}")
                st.caption(f"Evidência: {h.evidencia or 'sem evidência direta'}")


def _bloco_acoes(analise) -> None:
    if not analise.acoes_sugeridas:
        return
    st.markdown("**Ações sugeridas**")
    for acao in analise.acoes_sugeridas:
        with st.container(border=True):
            st.markdown(f"{selo('Não executada', 'gray')} {selo_risco(acao.risco)} {acao.acao}")
            detalhe = acao.motivo + (f" Runbook: {acao.runbook}." if acao.runbook else "")
            st.caption(detalhe)


def _desenhar_resposta(resposta) -> None:
    if resposta.aviso:
        st.error(
            f"**O auditor reprovou esta resposta.** {resposta.aviso}", icon=":material/gpp_bad:"
        )
    for item in dados_faltantes(resposta):
        st.info(f"**Preciso deste dado para continuar:** {item}", icon=":material/help:")
    analise = resposta.analise
    if analise is not None:
        st.markdown(f"{selo_severidade(analise.severidade)} {selo(analise.categoria, 'blue')}")
        st.markdown(analise.resumo)
        _bloco_hipoteses(analise)
        if analise.proximos_passos:
            st.markdown("**Próximos passos**")
            st.markdown("\n".join(f"1. {p}" for p in analise.proximos_passos))
        _bloco_acoes(analise)
    elif resposta.fixa is not None:
        st.markdown(resposta.fixa.texto)
    else:
        st.error(f"**Erro na investigação:** {resposta.erro or 'sem detalhes'}")
    fontes = fontes_consultadas(resposta)
    rodape = selo_auditor(resposta)
    if fontes:
        rodape += f" Fontes: {', '.join(fontes)}"
    st.caption(rodape)


# --- Aba de uso ---


def _historico(mensagens: list[dict]) -> None:
    for msg in mensagens:
        with st.chat_message(msg["papel"]):
            if msg["papel"] == "user":
                st.markdown(msg["texto"])
            elif msg.get("erro"):
                st.error(msg["erro"], icon=":material/error:")
            else:
                _desenhar_resposta(msg["resposta"])
                if msg["resposta"].trajetoria:
                    with st.expander(f"Passos da investigação ({_seg(msg['segundos'])})"):
                        st.markdown("\n".join(linhas_passos(msg["resposta"].trajetoria)))


def _tela_vazia() -> None:
    st.markdown(
        "Descreva o incidente ou cole o erro. O agente consulta logs, métricas, deploys e "
        "o histórico, e responde com a causa provável e as evidências."
    )
    st.markdown("**Sugestões para começar**")
    servico = st.session_state.cenario.get("servico")
    colunas = st.columns(2)
    for i, texto in enumerate(sugestoes_iniciais(servico)):
        if colunas[i % 2].button(texto, key=f"sugestao_{i}", width="stretch"):
            st.session_state.pendente = texto
            st.rerun()


def _responder(agente, pergunta: str) -> None:
    st.session_state.mensagens.append({"papel": "user", "texto": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)
    with st.chat_message("assistant"):
        inicio = time.perf_counter()
        with st.status("Investigando...", expanded=True) as status:
            st.write("Checando a mensagem e identificando a intenção e o serviço.")
            st.write("Consultando as ferramentas e o auditor. Isso leva de 10 a 60 segundos.")
            try:
                resposta = agente.turno(st.session_state.sessao, pergunta)
            except Exception as excecao:  # erro inesperado: mostra texto legível, sem pilha
                texto = mensagem_erro(excecao)
                status.update(label="A investigação falhou", state="error", expanded=False)
                st.error(texto, icon=":material/error:")
                st.session_state.mensagens.append({"papel": "assistant", "erro": texto})
                return
            segundos = time.perf_counter() - inicio
            for linha in linhas_passos(resposta.trajetoria):
                st.markdown(linha)
            n = len(resposta.trajetoria)
            status.update(
                label=f"Investigação concluída em {_seg(segundos)} ({n} consultas)",
                state="complete",
                expanded=False,
            )
        _desenhar_resposta(resposta)
    st.session_state.mensagens.append(
        {"papel": "assistant", "resposta": resposta, "segundos": segundos}
    )
    st.session_state.ultima_resposta = resposta


def _aba_uso(agente) -> None:
    conversa = st.container()
    pergunta = st.chat_input("Descreva o incidente ou faça uma pergunta")
    pergunta = pergunta or st.session_state.pop("pendente", None)
    with conversa:
        if not st.session_state.mensagens and not pergunta:
            _tela_vazia()
        _historico(st.session_state.mensagens)
        if pergunta:
            _responder(agente, pergunta)


# --- Aba de análise ---


def _passos_detalhados(passos) -> None:
    if not passos:
        st.caption("Este turno não chamou ferramentas.")
        return
    for i, passo in enumerate(passos, start=1):
        titulo = f"{i}. {rotulo_ferramenta(passo.ferramenta)} · {passo.duracao_ms} ms"
        with st.expander(titulo):
            st.markdown(f"Ferramenta: `{passo.ferramenta}` · {passo.tamanho} caracteres")
            if passo.erro:
                st.error(passo.erro)
            if passo.reserva:
                st.warning(f"Usou dados gravados: {passo.motivo_reserva or 'sem motivo'}")
            st.json(passo.argumentos, expanded=False)


def _auditoria_detalhada(turno) -> None:
    if turno.auditoria_aprovada is None:
        st.caption("Turno sem auditoria (resposta fixa ou sem investigação).")
    elif turno.auditoria_aprovada:
        st.success("Auditor aprovou a resposta.", icon=":material/verified:")
    else:
        st.error("Auditor reprovou a resposta.", icon=":material/gpp_bad:")
    if turno.aviso:
        st.markdown(f"**Aviso mostrado ao engenheiro:** {turno.aviso}")
    for motivo in turno.motivos_auditoria:
        st.markdown(f"- {motivo}")


def _detalhe_turno(turno) -> None:
    resposta, trajetoria, auditor = st.tabs(["Resposta", "Trajetória", "Auditor"])
    with resposta:
        st.markdown(f"**Pergunta:** {turno.pergunta}")
        st.markdown(turno.resposta)
    with trajetoria:
        _passos_detalhados(turno.trajetoria)
    with auditor:
        _auditoria_detalhada(turno)


def _aba_analise(agente) -> None:
    registros = agente.registro.listar()
    if not registros:
        st.info("Nenhum turno registrado ainda. Converse na aba Uso.", icon=":material/info:")
        return
    auditados = [r for r in registros if r.auditoria_aprovada is not None]
    aprovados = sum(1 for r in auditados if r.auditoria_aprovada)
    media = sum(r.duracao_ms for r in registros) / len(registros) / 1000
    c1, c2, c3 = st.columns(3)
    c1.metric("Turnos", len(registros))
    c2.metric("Aprovados pelo auditor", f"{aprovados} de {len(auditados)}")
    c3.metric("Duração média", _seg(media))
    with st.expander("Tabela de turnos", expanded=True):
        st.dataframe(linhas_registro(registros), width="stretch", hide_index=True)
    indice = st.selectbox(
        "Turno para detalhar",
        range(len(registros)),
        index=len(registros) - 1,
        format_func=lambda i: f"{i + 1}. {registros[i].pergunta[:70]}",
    )
    _detalhe_turno(registros[indice])


def main() -> None:
    st.set_page_config(page_title="Agente de incidentes", layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("Agente de análise de incidentes")
    _exigir_chave()
    agente = obter_agente()
    _barra_lateral(agente)
    uso, analise = st.tabs(["Uso", "Análise"])
    with uso:
        _aba_uso(agente)
    with analise:
        _aba_analise(agente)


main()
