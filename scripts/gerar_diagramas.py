"""Gera os diagramas (estilo C4 simples) em docs/img/: contexto.png e componentes.png."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch
from matplotlib.lines import Line2D

SAIDA = Path(__file__).resolve().parent.parent / "docs" / "img"
TXT = "#1f2933"

COR_PESSOA = ("#dbe7f5", "#2b5d9b")
COR_SISTEMA = ("#cfe3f7", "#1f4e8c")
COR_SEM_LLM = ("#d6ecd9", "#3b7d4a")
COR_LLM = ("#e4d8f3", "#6b46a8")
COR_EXTERNO = ("#e3e5e8", "#5a636e")
COR_FIXA = ("#fbe3b8", "#b9770e")
COR_FASE2 = ("#f4f5f6", "#a3aab2")


def nova_figura(larg, alt, xmax, ymax, ymin=0):
    fig, ax = plt.subplots(figsize=(larg, alt), dpi=150)
    ax.set_xlim(0, xmax)
    ax.set_ylim(ymin, ymax)
    ax.axis("off")
    return fig, ax


def caixa(ax, x, y, w, h, cores, titulo, detalhe="", tracejada=False, cor_txt=TXT):
    """Retângulo arredondado com título em negrito e detalhe abaixo."""
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.8", fc=cores[0], ec=cores[1],
        lw=1.8, ls="--" if tracejada else "-", zorder=2))
    cx = x + w / 2
    if detalhe:
        ax.text(cx, y + h - 1.2, titulo, ha="center", va="top", fontsize=10.5,
                fontweight="bold", color=cor_txt, zorder=3, linespacing=1.3)
        ax.text(cx, y + h - 3.8, detalhe, ha="center", va="top", fontsize=8.8,
                color=cor_txt, zorder=3, linespacing=1.35)
    else:
        ax.text(cx, y + h / 2, titulo, ha="center", va="center", fontsize=10.5,
                fontweight="bold", color=cor_txt, zorder=3, linespacing=1.3)


def seta(ax, p0, p1, rotulo="", externa=False, cor="#374151", pos="acima", ha="center",
         tam=8.5, dx=0, dy=0):
    """Seta cheia (interna) ou tracejada (externa) com rótulo."""
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle="-|>", mutation_scale=14, lw=1.6, color=cor,
        ls=(0, (5, 3)) if externa else "-", zorder=1, shrinkA=0, shrinkB=0))
    if not rotulo:
        return
    mx, my = (p0[0] + p1[0]) / 2 + dx, (p0[1] + p1[1]) / 2 + dy
    va = {"acima": "bottom", "abaixo": "top", "meio": "center"}[pos]
    off = {"acima": 0.5, "abaixo": -0.5, "meio": 0}[pos]
    ax.text(mx, my + off, rotulo, ha=ha, va=va, fontsize=tam, color=cor, zorder=4,
            linespacing=1.3, bbox=dict(fc="white", ec="none", pad=1.2, alpha=0.9))


def legenda(ax, itens, x, y, larg_col, ncol=1, titulo="Legenda"):
    """Legenda desenhada dentro da imagem (lista de (rótulo, cores, tracejada|None))."""
    ax.text(x, y, titulo, fontsize=10.5, fontweight="bold", color=TXT, va="top")
    for i, (rot, cores, estilo) in enumerate(itens):
        c, l = divmod(i, (len(itens) + ncol - 1) // ncol)
        xi, yi = x + c * larg_col, y - 2.6 - l * 2.4
        if cores:
            ax.add_patch(FancyBboxPatch((xi, yi - 0.8), 3, 1.6, boxstyle="round,pad=0,rounding_size=0.3",
                                        fc=cores[0], ec=cores[1], lw=1.5,
                                        ls="--" if estilo else "-"))
        else:
            ax.plot([xi, xi + 3], [yi, yi], color="#374151", lw=1.8,
                    ls=(0, (5, 3)) if estilo else "-")
        ax.text(xi + 3.8, yi, rot, fontsize=8.8, va="center", color=TXT)


def contexto():
    fig, ax = nova_figura(18, 11, 100, 58, -10)
    ax.text(50, 56.5, "incident-agent: diagrama de contexto", ha="center", va="top",
            fontsize=15, fontweight="bold", color=TXT)
    caixa(ax, 2, 25, 19, 12, COR_PESSOA, "Engenheiro de plantão", "[pessoa]\ninvestiga o incidente")
    caixa(ax, 33, 12, 27, 36, COR_SISTEMA, "incident-agent",
          "(agente investigador\nde incidentes)\n\n[sistema]\nmascara, modera, entende a\nintenção e investiga a causa")
    seta(ax, (21, 33), (33, 33), "pergunta +\nhistórico")
    seta(ax, (33, 29), (21, 29), "resposta fixa ou\nanálise JSON", pos="abaixo")
    ext = [
        (42, "OpenAI Moderation API\n(omni-moderation-latest)", COR_EXTERNO, False,
         "texto mascarado", "pontuação por\ncategoria"),
        (32, "API de chat: OpenAI (gpt-4o-mini)\nou DeepSeek (deepseek-v4-flash)", COR_EXTERNO, False,
         "prompt", "análise em JSON"),
        (22, "GitHub API [Fase 2]", COR_FASE2, True, "consulta de\ncódigo (futuro)", "código e\ncommits"),
        (12, "incident-shop (LOJA_URL)\n[Fase 2]", COR_FASE2, True, "consulta de\nestado (futuro)", "dados da loja"),
    ]
    for yc, nome, cores, fase2, ida, volta in ext:
        caixa(ax, 76, yc - 3.5, 22, 7, cores, nome, tracejada=fase2,
              cor_txt="#6b7280" if fase2 else TXT)
        cor = "#8a929b" if fase2 else "#374151"
        seta(ax, (60, yc + 1.4), (76, yc + 1.4), ida, externa=True, cor=cor, tam=8)
        seta(ax, (76, yc - 1.4), (60, yc - 1.4), volta, externa=True, cor=cor, pos="abaixo", tam=8)
    legenda(ax, [
        ("pessoa", COR_PESSOA, None), ("sistema (nosso)", COR_SISTEMA, None),
        ("serviço externo da Fase 1", COR_EXTERNO, None),
        ("serviço externo da Fase 2 (futuro, borda tracejada)", COR_FASE2, True),
        ("seta cheia: interação direta do usuário", None, None),
        ("seta tracejada: chamada externa pela rede", None, True),
    ], 2, 9, 0, ncol=1)
    fig.savefig(SAIDA / "contexto.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


PASSOS = [
    ("1  máscara", "mascarar()  (regex local)\ninterno, sem modelo de linguagem", COR_SEM_LLM),
    ("2  mensagem vazia", "_decide_vazia\nchecagem interna, sem modelo de linguagem", COR_SEM_LLM),
    ("3  moderação", "moderar()  com limiar por categoria (LIMIARES)\nchama serviço EXTERNO", COR_SEM_LLM),
    ("4  compreensão de linguagem natural",
     "montar_nlu: ChatPromptTemplate | llm.with_structured_output(AnaliseNLU)\nchama modelo de linguagem (API de chat EXTERNA)", COR_LLM),
    ("5  roteador", "RunnableBranch, interno, sem modelo de linguagem\nlê só e[\"nlu\"].intencao em INTENCOES_FIXAS", COR_SEM_LLM),
    ("6  investigação",
     "preprocessar() + prompt + modelo + JsonOutputParser -> AnaliseIncidente\nchama modelo de linguagem (API de chat EXTERNA); with_retry: 1 nova tentativa", COR_LLM),
    ("7  resposta", "monta RespostaTurno\ninterno, sem modelo de linguagem", COR_SEM_LLM),
]


def componentes():
    H, GAP, X, W = 9, 8.5, 31, 40
    topo = 137
    ys = [topo - i * (H + GAP) - H for i in range(7)]  # base de cada caixa
    fig, ax = nova_figura(18, 26, 100, 148, -12)
    ax.text(50, 147, "incident-agent: componentes da chain (pipeline)", ha="center", va="top",
            fontsize=15, fontweight="bold", color=TXT)
    for (tit, det, cor), y in zip(PASSOS, ys):
        caixa(ax, X, y, W, H, (cor[0], cor[1]), tit, det)
    cx, mid = X + W / 2, [y + H / 2 for y in ys]
    # entrada
    seta(ax, (cx, ys[0] + H + 6), (cx, ys[0] + H), "entrada: {mensagem, historico}  (INTERNA: chamada do pipeline)",
         pos="meio", dx=0.0, dy=3.2 - 3.2, ha="left")
    # setas verticais (chaves do dicionário + tipo de chamada)
    rot = [
        "{mensagem, historico} mascarados\nINTERNA: função",
        "+ resposta (None ou RespostaTurno)\nINTERNA: função",
        "+ moderacao (ResultadoModeracao)\n+ resposta\nINTERNA: classe/função",
        "+ nlu (AnaliseNLU)\nINTERNA: função",
        "+ resposta (None ou RespostaTurno)\nINTERNA: função",
        "+ resultado (AnaliseIncidente ou erro)\n+ resposta\nINTERNA: função",
    ]
    for i, r in enumerate(rot):
        seta(ax, (cx, ys[i]), (cx, ys[i + 1] + H), r, pos="meio", ha="left", dx=1.0)
    seta(ax, (cx, ys[6]), (cx, ys[6] - 6), "RespostaTurno  (saída)\nINTERNA: função", pos="meio", ha="left", dx=1.0)
    # resposta fixa (esquerda)
    fy0, fy1 = ys[4] - 1, ys[1] + H + 1
    caixa(ax, 1, fy0, 17, fy1 - fy0, COR_FIXA, "Resposta fixa",
          "RespostaFixa(texto, camada,\ncategoria) a partir de\nrespostas_fixas\n\ncamada 1: sinalizada\n(passo 3)\ncamada 2: vazia (passo 2),\nintenção fixa (passo 5)\n\nsem modelo de linguagem;\nsegue pelo estado\naté o passo 7")
    for i, r in [(1, "camada 2: vazia\nINTERNA: função"), (2, "camada 1: sinalizada\nINTERNA: função"),
                 (4, "camada 2: intenção fixa\nINTERNA: função")]:
        seta(ax, (X, mid[i]), (18, mid[i]), r, pos="acima", tam=8, dx=0)
    # externos (direita)
    caixa(ax, 82, ys[2] - 1, 17, H + 2, COR_EXTERNO, "OpenAI Moderation API", "omni-moderation-latest\n(serviço externo)")
    seta(ax, (X + W, mid[2] + 1.8), (82, mid[2] + 1.8), "EXTERNA:\nmoderar(mensagem)", externa=True, tam=8)
    seta(ax, (82, mid[2] - 1.8), (X + W, mid[2] - 1.8), "category_scores", externa=True, pos="abaixo", tam=8)
    cy0, cy1 = ys[5] - 1, ys[3] + H + 1
    caixa(ax, 82, cy0, 17, cy1 - cy0, COR_EXTERNO, "API de chat",
          "OpenAI (gpt-4o-mini)\nou DeepSeek\n(deepseek-v4-flash)\n\nserviço externo")
    for i, ida, volta in [(3, "EXTERNA: prompt\n(passo 4)", "AnaliseNLU\nestruturada"),
                          (5, "EXTERNA: prompt\n(passo 6)", "JSON da\nanálise")]:
        seta(ax, (X + W, mid[i] + 1.8), (82, mid[i] + 1.8), ida, externa=True, tam=8)
        seta(ax, (82, mid[i] - 1.8), (X + W, mid[i] - 1.8), volta, externa=True, pos="abaixo", tam=8)
    legenda(ax, [
        ("componente nosso, sem modelo de linguagem", COR_SEM_LLM, None),
        ("componente nosso que chama modelo de linguagem", COR_LLM, None),
        ("serviço externo", COR_EXTERNO, None),
        ("respostas fixas", COR_FIXA, None),
        ("seta cheia: chamada interna (função, regex ou classe)", None, None),
        ("seta tracejada: chamada externa (rede)", None, True),
    ], 25, ys[6] - 12, 0)
    fig.savefig(SAIDA / "componentes.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    SAIDA.mkdir(parents=True, exist_ok=True)
    contexto()
    componentes()
    print("gerados:", SAIDA / "contexto.png", SAIDA / "componentes.png")
