"""Gera os diagramas (estilo C4 simples) em docs/img/: contexto.png e componentes.png."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch
from matplotlib.lines import Line2D

SAIDA = Path(__file__).resolve().parent.parent / "docs" / "img"
TXT = "#1f2933"

# Paleta única dos dois diagramas: papel -> (fundo claro, borda/cor forte).
# Cores fortes validadas com o validador de paleta da skill dataviz (modo claro, fundo branco,
# todos os pares): pessoa, nosso sistema, componente com modelo de linguagem e respostas fixas
# passam em faixa de luminosidade, croma, separação para daltonismo (pior ΔE 8,1), separação
# para visão normal (pior ΔE 21,5) e contraste >= 3:1. Externos ficam em cinza neutro (convenção
# C4) e o futuro em cinza mais claro com borda tracejada (codificação secundária).
# O fundo de cada caixa é a cor forte diluída em branco; o texto é sempre escuro (TXT).
PALETA = {
    "pessoa":  ("#f3dbea", "#b0368a"),   # magenta-ameixa
    "sistema": ("#d9e7f8", "#2a78d6"),   # azul: nosso sistema e nossos componentes sem modelo
    "llm":     ("#d5eee4", "#159a6b"),   # verde-azulado: nosso componente que chama o modelo
    "fixa":    ("#fbe5d4", "#e8701f"),   # laranja: respostas fixas
    "externo": ("#e8e9ea", "#5f6368"),   # cinza: serviço externo da Fase 1
    "futuro":  ("#f6f7f8", "#9aa0a6"),   # cinza claro + tracejado: serviço externo futuro
}
COR_PESSOA = PALETA["pessoa"]
COR_SISTEMA = PALETA["sistema"]
COR_SEM_LLM = PALETA["sistema"]
COR_LLM = PALETA["llm"]
COR_EXTERNO = PALETA["externo"]
COR_FIXA = PALETA["fixa"]
COR_FASE2 = PALETA["futuro"]


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
    fig, ax = nova_figura(18, 8, 100, 47, 1)
    ax.text(50, 46, "incident-agent: diagrama de contexto", ha="center", va="top",
            fontsize=15, fontweight="bold", color=TXT)
    # pessoa e sistema na mesma faixa (centro y=32); externos da Fase 1 à direita, alinhados
    # com o sistema; externos futuros abaixo do sistema, com setas verticais.
    caixa(ax, 2, 27, 19, 10.5, COR_PESSOA, "Engenheiro de plantão", "[pessoa]\ninvestiga o incidente")
    caixa(ax, 33, 27, 27, 10.5, COR_SISTEMA, "incident-agent",
          "[sistema] agente investigador de incidentes\nmascara, modera, entende a intenção\ne investiga a causa")
    seta(ax, (21, 33.5), (33, 33.5), "pergunta +\nhistórico")
    seta(ax, (33, 30.5), (21, 30.5), "resposta fixa ou\nanálise JSON", pos="abaixo")
    for yc, nome, ida, volta in [
        (35.5, "OpenAI Moderation API\n(omni-moderation-latest)", "texto mascarado", "pontuação por categoria"),
        (28.5, "API de chat: OpenAI (gpt-4o-mini)\nou DeepSeek (deepseek-v4-flash)", "prompt", "análise em JSON"),
    ]:
        caixa(ax, 76, yc - 3, 22, 6, COR_EXTERNO, nome)
        seta(ax, (60, yc + 1.1), (76, yc + 1.1), ida, externa=True, tam=8)
        seta(ax, (76, yc - 1.1), (60, yc - 1.1), volta, externa=True, pos="abaixo", tam=8)
    cinza = PALETA["futuro"][1]
    for xc, nome, ida, volta in [
        (37.5, "GitHub API\n[Fase 2]", "consulta de\ncódigo", "código e\ncommits"),
        (55.5, "incident-shop (LOJA_URL)\n[Fase 2]", "consulta de\nestado", "dados da\nloja"),
    ]:
        caixa(ax, xc - 8.5, 3, 17, 7, COR_FASE2, nome, tracejada=True, cor_txt="#4b5563")
        seta(ax, (xc - 1.2, 27), (xc - 1.2, 10), ida, externa=True, cor=cinza, pos="meio",
             ha="right", tam=8, dx=-0.6)
        seta(ax, (xc + 1.2, 10), (xc + 1.2, 27), volta, externa=True, cor=cinza, pos="meio",
             ha="left", tam=8, dx=0.6)
    legenda(ax, [
        ("pessoa", COR_PESSOA, None), ("sistema (nosso)", COR_SISTEMA, None),
        ("serviço externo da Fase 1", COR_EXTERNO, None),
        ("serviço externo da Fase 2 (futuro, borda tracejada)", COR_FASE2, True),
        ("seta cheia: interação direta do usuário", None, None),
        ("seta tracejada: chamada externa pela rede", None, True),
    ], 68, 20, 0, ncol=1)
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
