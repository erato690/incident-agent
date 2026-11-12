"""Gera os diagramas (estilo C4 simples) em docs/img/.

Arquivos: contexto.png, componentes.png, componentes_fase2.png, componentes_fase3.png,
componentes_fase4.png e arquitetura_final.png.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

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
    "pessoa": ("#f3dbea", "#b0368a"),  # magenta-ameixa
    "sistema": ("#d9e7f8", "#2a78d6"),  # azul: nosso sistema e nossos componentes sem modelo
    "llm": ("#d5eee4", "#159a6b"),  # verde-azulado: nosso componente que chama o modelo
    "fixa": ("#fbe5d4", "#e8701f"),  # laranja: respostas fixas
    "externo": ("#e8e9ea", "#5f6368"),  # cinza: serviço externo da Fase 1
    "futuro": ("#f6f7f8", "#9aa0a6"),  # cinza claro + tracejado: reservado (hoje sem uso)
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
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0,rounding_size=0.8",
            fc=cores[0],
            ec=cores[1],
            lw=1.8,
            ls="--" if tracejada else "-",
            zorder=2,
        )
    )
    centro_x = x + w / 2
    if detalhe:
        ax.text(
            centro_x,
            y + h - 1.2,
            titulo,
            ha="center",
            va="top",
            fontsize=10.5,
            fontweight="bold",
            color=cor_txt,
            zorder=3,
            linespacing=1.3,
        )
        ax.text(
            centro_x,
            y + h - 3.8,
            detalhe,
            ha="center",
            va="top",
            fontsize=8.8,
            color=cor_txt,
            zorder=3,
            linespacing=1.35,
        )
    else:
        ax.text(
            centro_x,
            y + h / 2,
            titulo,
            ha="center",
            va="center",
            fontsize=10.5,
            fontweight="bold",
            color=cor_txt,
            zorder=3,
            linespacing=1.3,
        )


def seta(
    ax,
    p0,
    p1,
    rotulo="",
    externa=False,
    cor="#374151",
    pos="acima",
    ha="center",
    tam=8.5,
    dx=0,
    dy=0,
    estilo="-|>",
):
    """Seta cheia (interna) ou tracejada (externa) com rótulo."""
    ax.add_patch(
        FancyArrowPatch(
            p0,
            p1,
            arrowstyle=estilo,
            mutation_scale=14,
            lw=1.6,
            color=cor,
            ls=(0, (5, 3)) if externa else "-",
            zorder=1,
            shrinkA=0,
            shrinkB=0,
        )
    )
    if not rotulo:
        return
    mx, my = (p0[0] + p1[0]) / 2 + dx, (p0[1] + p1[1]) / 2 + dy
    va = {"acima": "bottom", "abaixo": "top", "meio": "center"}[pos]
    off = {"acima": 0.5, "abaixo": -0.5, "meio": 0}[pos]
    ax.text(
        mx,
        my + off,
        rotulo,
        ha=ha,
        va=va,
        fontsize=tam,
        color=cor,
        zorder=4,
        linespacing=1.3,
        bbox=dict(fc="white", ec="none", pad=1.2, alpha=0.9),
    )


def legenda(ax, itens, x, y, larg_col, ncol=1, titulo="Legenda"):
    """Legenda desenhada dentro da imagem (lista de (rótulo, cores, tracejada|None))."""
    ax.text(x, y, titulo, fontsize=10.5, fontweight="bold", color=TXT, va="top")
    for i, (rot, cores, estilo) in enumerate(itens):
        coluna, linha_na_coluna = divmod(i, (len(itens) + ncol - 1) // ncol)
        xi, yi = x + coluna * larg_col, y - 2.6 - linha_na_coluna * 2.4
        if cores:
            ax.add_patch(
                FancyBboxPatch(
                    (xi, yi - 0.8),
                    3,
                    1.6,
                    boxstyle="round,pad=0,rounding_size=0.3",
                    fc=cores[0],
                    ec=cores[1],
                    lw=1.5,
                    ls="--" if estilo else "-",
                )
            )
        else:
            ax.plot(
                [xi, xi + 3], [yi, yi], color="#374151", lw=1.8, ls=(0, (5, 3)) if estilo else "-"
            )
        ax.text(xi + 3.8, yi, rot, fontsize=8.8, va="center", color=TXT)


def contexto():
    fig, ax = nova_figura(18, 8.6, 100, 47, -2)
    ax.text(
        50,
        46,
        "incident-agent: diagrama de contexto",
        ha="center",
        va="top",
        fontsize=15,
        fontweight="bold",
        color=TXT,
    )
    # pessoa e sistema na mesma faixa (centro y=32); externos da Fase 1 à direita, alinhados
    # com o sistema; externos da Fase 2 abaixo do sistema, com setas verticais.
    caixa(
        ax, 2, 27, 19, 10.5, COR_PESSOA, "Engenheiro de plantão", "[pessoa]\ninvestiga o incidente"
    )
    caixa(
        ax,
        33,
        27,
        27,
        10.5,
        COR_SISTEMA,
        "incident-agent",
        "[sistema] agente investigador de incidentes\n"
        "mascara, modera, entende a intenção\ne investiga a causa",
    )
    seta(ax, (21, 33.5), (33, 33.5), "pergunta +\nhistórico")
    seta(ax, (33, 30.5), (21, 30.5), "resposta fixa ou\nanálise JSON", pos="abaixo")
    for y_centro, nome, ida, volta in [
        (
            35.5,
            "OpenAI Moderation API\n(omni-moderation-latest)",
            "texto mascarado",
            "pontuação por categoria",
        ),
        (
            28.5,
            "API de chat: OpenAI (gpt-4o-mini)\nou DeepSeek (deepseek-v4-flash)",
            "prompt",
            "análise em JSON",
        ),
    ]:
        caixa(ax, 76, y_centro - 3, 22, 6, COR_EXTERNO, nome)
        seta(ax, (60, y_centro + 1.1), (76, y_centro + 1.1), ida, externa=True, tam=8)
        seta(
            ax, (76, y_centro - 1.1), (60, y_centro - 1.1), volta, externa=True, pos="abaixo", tam=8
        )
    # serviços externos da Fase 2 (reais): cor do externo, sem tracejado, com nota de reserva
    caixa(
        ax,
        8,
        -1,
        32,
        10,
        COR_EXTERNO,
        "GitHub API",
        "[serviço externo]\nsem rede: comparação gravada\n(dados_dummy/github/)",
    )
    caixa(
        ax,
        46,
        -1,
        34,
        10,
        COR_EXTERNO,
        "incident-shop (LOJA_URL)",
        "[serviço externo]\nsem LOJA_URL: respostas gravadas\nem dados_dummy/",
    )
    for x_ida, x_volta, ida, volta, ha_ida, ha_volta in [
        (
            34,
            37.5,
            "GET compare/{base}...{nova} (tags)",
            "commits, arquivos\ne trechos do diff",
            "right",
            "left",
        ),
        (
            56,
            60,
            "GET /logs, /metricas,\n/deploys (serviço +\njanela do cenário)",
            "logs, séries de\nmétricas, deploys",
            "right",
            "left",
        ),
    ]:
        seta(ax, (x_ida, 27), (x_ida, 9), ida, externa=True, pos="meio", ha=ha_ida, tam=8, dx=-0.6)
        seta(
            ax,
            (x_volta, 9),
            (x_volta, 27),
            volta,
            externa=True,
            pos="meio",
            ha=ha_volta,
            tam=8,
            dx=0.6,
        )
    legenda(
        ax,
        [
            ("pessoa", COR_PESSOA, None),
            ("sistema (nosso)", COR_SISTEMA, None),
            ("serviço externo (Fases 1 e 2)", COR_EXTERNO, None),
            ("seta cheia: interação direta do usuário", None, None),
            ("seta tracejada: chamada externa pela rede", None, True),
        ],
        82,
        22,
        0,
        ncol=1,
    )
    fig.savefig(SAIDA / "contexto.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


PASSOS = [
    ("1  máscara", "mascarar()  (regex local)\ninterno, sem modelo de linguagem", COR_SEM_LLM),
    ("2  mensagem vazia", "_decide_vazia\nchecagem interna, sem modelo de linguagem", COR_SEM_LLM),
    (
        "3  moderação",
        "moderar()  com limiar por categoria (LIMIARES)\nchama serviço EXTERNO",
        COR_SEM_LLM,
    ),
    (
        "4  compreensão de linguagem natural",
        "montar_nlu: ChatPromptTemplate | llm.with_structured_output(AnaliseNLU)\n"
        "chama modelo de linguagem (API de chat EXTERNA)",
        COR_LLM,
    ),
    (
        "5  roteador",
        "RunnableBranch, interno, sem modelo de linguagem\n"
        'lê só e["nlu"].intencao em INTENCOES_FIXAS',
        COR_SEM_LLM,
    ),
    (
        "6  investigação",
        "preprocessar() + prompt + modelo + JsonOutputParser -> AnaliseIncidente\n"
        "chama modelo de linguagem (API de chat EXTERNA); with_retry: 1 nova tentativa",
        COR_LLM,
    ),
    ("7  resposta", "monta RespostaTurno\ninterno, sem modelo de linguagem", COR_SEM_LLM),
]


def componentes():
    altura, intervalo, x_caixa, largura = 9, 8.5, 31, 40
    topo = 137
    ys = [topo - i * (altura + intervalo) - altura for i in range(7)]  # base de cada caixa
    fig, ax = nova_figura(18, 26, 100, 148, -12)
    ax.text(
        50,
        147,
        "incident-agent: componentes da chain (pipeline)",
        ha="center",
        va="top",
        fontsize=15,
        fontweight="bold",
        color=TXT,
    )
    for (tit, det, cor), y in zip(PASSOS, ys, strict=True):
        caixa(ax, x_caixa, y, largura, altura, (cor[0], cor[1]), tit, det)
    centro_x, mid = x_caixa + largura / 2, [y + altura / 2 for y in ys]
    # entrada
    seta(
        ax,
        (centro_x, ys[0] + altura + 6),
        (centro_x, ys[0] + altura),
        "entrada: {mensagem, historico}  (INTERNA: chamada do pipeline)",
        pos="meio",
        dx=0.0,
        dy=3.2 - 3.2,
        ha="left",
    )
    # setas verticais (chaves do dicionário + tipo de chamada)
    rot = [
        "{mensagem, historico} mascarados\nINTERNA: função",
        "+ resposta (None ou RespostaTurno)\nINTERNA: função",
        "+ moderacao (ResultadoModeracao)\n+ resposta\nINTERNA: classe/função",
        "+ nlu (AnaliseNLU)\nINTERNA: função",
        "+ resposta (None ou RespostaTurno)\nINTERNA: função",
        "+ resultado (AnaliseIncidente ou erro)\n+ resposta\nINTERNA: função",
    ]
    for indice, rotulo in enumerate(rot):
        seta(
            ax,
            (centro_x, ys[indice]),
            (centro_x, ys[indice + 1] + altura),
            rotulo,
            pos="meio",
            ha="left",
            dx=1.0,
        )
    seta(
        ax,
        (centro_x, ys[6]),
        (centro_x, ys[6] - 6),
        "RespostaTurno  (saída)\nINTERNA: função",
        pos="meio",
        ha="left",
        dx=1.0,
    )
    # resposta fixa (esquerda)
    fy0, fy1 = ys[4] - 1, ys[1] + altura + 1
    caixa(
        ax,
        1,
        fy0,
        17,
        fy1 - fy0,
        COR_FIXA,
        "Resposta fixa",
        "RespostaFixa(texto, camada,\ncategoria) a partir de\nrespostas_fixas\n\n"
        "camada 1: sinalizada\n(passo 3)\ncamada 2: vazia (passo 2),\n"
        "intenção fixa (passo 5)\n\nsem modelo de linguagem;\nsegue pelo estado\naté o passo 7",
    )
    for indice, rotulo in [
        (1, "camada 2: vazia\nINTERNA: função"),
        (2, "camada 1: sinalizada\nINTERNA: função"),
        (4, "camada 2: intenção fixa\nINTERNA: função"),
    ]:
        seta(ax, (x_caixa, mid[indice]), (18, mid[indice]), rotulo, pos="acima", tam=8, dx=0)
    # externos (direita)
    caixa(
        ax,
        82,
        ys[2] - 1,
        17,
        altura + 2,
        COR_EXTERNO,
        "OpenAI Moderation API",
        "omni-moderation-latest\n(serviço externo)",
    )
    seta(
        ax,
        (x_caixa + largura, mid[2] + 1.8),
        (82, mid[2] + 1.8),
        "EXTERNA:\nmoderar(mensagem)",
        externa=True,
        tam=8,
    )
    seta(
        ax,
        (82, mid[2] - 1.8),
        (x_caixa + largura, mid[2] - 1.8),
        "category_scores",
        externa=True,
        pos="abaixo",
        tam=8,
    )
    cy0, cy1 = ys[5] - 1, ys[3] + altura + 1
    caixa(
        ax,
        82,
        cy0,
        17,
        cy1 - cy0,
        COR_EXTERNO,
        "API de chat",
        "OpenAI (gpt-4o-mini)\nou DeepSeek\n(deepseek-v4-flash)\n\nserviço externo",
    )
    for indice, ida, volta in [
        (3, "EXTERNA: prompt\n(passo 4)", "AnaliseNLU\nestruturada"),
        (5, "EXTERNA: prompt\n(passo 6)", "JSON da\nanálise"),
    ]:
        seta(
            ax,
            (x_caixa + largura, mid[indice] + 1.8),
            (82, mid[indice] + 1.8),
            ida,
            externa=True,
            tam=8,
        )
        seta(
            ax,
            (82, mid[indice] - 1.8),
            (x_caixa + largura, mid[indice] - 1.8),
            volta,
            externa=True,
            pos="abaixo",
            tam=8,
        )
    legenda(
        ax,
        [
            ("componente nosso, sem modelo de linguagem", COR_SEM_LLM, None),
            ("componente nosso que chama modelo de linguagem", COR_LLM, None),
            ("serviço externo", COR_EXTERNO, None),
            ("respostas fixas", COR_FIXA, None),
            ("seta cheia: chamada interna (função, regex ou classe)", None, None),
            ("seta tracejada: chamada externa (rede)", None, True),
        ],
        25,
        ys[6] - 12,
        0,
    )
    fig.savefig(SAIDA / "componentes.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


FERRAMENTAS = [
    (
        "buscar_logs",
        "(servico, nivel)",
        "incident-shop",
        "(LOJA_URL)",
        "ida: GET /logs\nvolta: logs",
        "sem LOJA_URL",
    ),
    (
        "buscar_metricas",
        "(servico, metrica)",
        "incident-shop",
        "(LOJA_URL)",
        "ida: GET /metricas\nvolta: séries",
        "sem LOJA_URL",
    ),
    (
        "listar_deploys",
        "(servico)",
        "incident-shop",
        "(LOJA_URL)",
        "ida: GET /deploys\nvolta: deploys",
        "sem LOJA_URL",
    ),
    (
        "comparar_versoes",
        "(tag_base, tag_nova)",
        "GitHub API",
        "",
        "ida: GET compare/\n{base}...{nova}\nvolta: commits,\narquivos, trechos",
        "sem rede",
    ),
]


def linha(ax, pts, rotulo="", xr=None, yr=None, ha="left", tam=8):
    """Seta em ângulo reto: segmentos retos e ponta no último ponto."""
    for inicio, fim in zip(pts[:-2], pts[1:-1], strict=True):
        ax.plot([inicio[0], fim[0]], [inicio[1], fim[1]], color="#374151", lw=1.6, zorder=1)
    seta(ax, pts[-2], pts[-1])
    if rotulo:
        ax.text(
            xr,
            yr,
            rotulo,
            ha=ha,
            va="center",
            fontsize=tam,
            color="#374151",
            zorder=4,
            linespacing=1.3,
            bbox=dict(fc="white", ec="none", pad=1.2, alpha=0.9),
        )


def _ferramentas_fase2(ax):
    for posicao, (nome, args, serv, nota, ext, res) in enumerate(FERRAMENTAS):
        x0 = 17 + posicao * 22
        xc = x0 + 10
        caixa(ax, x0, 43, 20, 9, COR_SEM_LLM, nome, args + "\ninterna, sem modelo de linguagem")
        seta(
            ax,
            (xc - 6, 66),
            (xc - 6, 52),
            args.strip("()").replace(", ", ",\n"),
            pos="meio",
            ha="right",
            tam=7.5,
            dx=-0.5,
        )
        seta(
            ax,
            (xc - 3, 52),
            (xc - 3, 66),
            "",
        )
        ax.text(
            xc - 2.4,
            59,
            "observação\nmascarada",
            ha="left",
            va="center",
            fontsize=7.5,
            color="#374151",
            zorder=4,
            linespacing=1.3,
            bbox=dict(fc="white", ec="none", pad=1, alpha=0.9),
        )
        caixa(ax, x0, 27, 9.6, 9, COR_EXTERNO, serv, nota)
        caixa(ax, x0 + 10.4, 27, 9.6, 9, COR_FIXA, "gravadas", "dados_dummy/")
        seta(
            ax,
            (x0 + 4.8, 43),
            (x0 + 4.8, 36),
            "EXTERNA\n" + ext,
            externa=True,
            pos="meio",
            ha="center",
            tam=7,
            estilo="<|-|>",
        )
        seta(
            ax,
            (x0 + 15.2, 43),
            (x0 + 15.2, 36),
            "INTERNA (reserva)\n" + res + ":\nlê arquivo",
            pos="meio",
            ha="center",
            tam=7,
        )


def componentes_fase2():
    fig, ax = nova_figura(27, 22, 140, 110, -24)
    ax.text(
        70,
        109.5,
        "incident-agent: componentes da Fase 2 (agente ReAct no passo 6)",
        ha="center",
        va="top",
        fontsize=15,
        fontweight="bold",
        color=TXT,
    )
    seta(
        ax,
        (74, 106),
        (74, 100),
        "entrada: {mensagem, historico}  (INTERNA: chamada do pipeline)",
        pos="meio",
        ha="left",
        dx=1,
    )
    caixa(
        ax,
        40,
        91,
        70,
        9,
        COR_SEM_LLM,
        "entrada da Fase 1 (passos 1 a 5)",
        "máscara, mensagem vazia, moderação, compreensão de linguagem natural, roteador\n"
        "(passos 3 e 4 chamam serviços externos; detalhes em componentes.png)",
    )
    seta(
        ax,
        (74, 91),
        (74, 80),
        "+ mensagem mascarada, historico, nlu  (INTERNA: função)",
        pos="meio",
        ha="left",
        dx=1,
    )
    caixa(
        ax,
        118,
        91,
        20,
        9,
        COR_FIXA,
        "Resposta fixa",
        "RespostaFixa (camada 1 ou 2)\nsem modelo de linguagem",
    )
    seta(ax, (110, 95.5), (118, 95.5), "INTERNA:\ntexto fixo", pos="acima", tam=7.5)
    seta(
        ax,
        (134, 91),
        (134, 3),
        "RespostaFixa\n(INTERNA: segue\npelo estado)",
        pos="meio",
        ha="left",
        dx=0.8,
        dy=-24,
        tam=8,
    )
    # container do passo 6
    ax.add_patch(
        FancyBboxPatch(
            (6, 24),
            100,
            64,
            boxstyle="round,pad=0,rounding_size=0.8",
            fc="none",
            ec=COR_SISTEMA[1],
            lw=1.4,
            ls=":",
            zorder=0,
        )
    )
    ax.text(
        7,
        87,
        "6  Investigador: montar_investigador (ReAct)",
        fontsize=10.5,
        fontweight="bold",
        color=TXT,
        va="top",
    )
    caixa(
        ax,
        17,
        66,
        86,
        14,
        COR_LLM,
        "agente ReAct (create_agent)",
        "prompt Persona-Tarefa-Contexto-Formato; ciclo: raciocina, chama ferramenta, observa\n"
        "limite de passos (max_passos = 8); observações mascaradas antes do modelo de linguagem\n"
        "chama modelo de linguagem (API de chat EXTERNA)",
    )
    caixa(
        ax,
        113,
        66,
        20,
        14,
        COR_EXTERNO,
        "Modelo de linguagem",
        "API de chat\nOpenAI (gpt-4o-mini)\nou DeepSeek\n(serviço externo)",
    )
    seta(ax, (103, 76.5), (113, 76.5), "EXTERNA:\nmensagens +\nferramentas", externa=True, tam=7.5)
    seta(
        ax,
        (113, 69.5),
        (103, 69.5),
        "EXTERNA: resposta\nou pedido de\nferramenta (ciclo)",
        externa=True,
        pos="abaixo",
        tam=7.5,
    )
    _ferramentas_fase2(ax)
    caixa(
        ax,
        113,
        43,
        20,
        9,
        COR_SEM_LLM,
        "TrajetoriaCallback",
        "registra cada chamada\n(interna, sem modelo)",
    )
    seta(ax, (103, 47.5), (113, 47.5), "INTERNA:\neventos das\nferramentas", pos="acima", tam=7.5)
    seta(
        ax,
        (123, 43),
        (123, 3),
        "trajetoria\n(INTERNA: lista\nde chamadas)",
        pos="meio",
        ha="left",
        dx=0.8,
        dy=-8,
        tam=8,
    )
    # parser (fora do container) e saída
    linha(
        ax,
        [(17, 73), (14, 73), (14, 11.5), (40, 11.5)],
        "texto final\nINTERNA",
        13.5,
        50,
        ha="right",
        tam=7.5,
    )
    caixa(
        ax,
        40,
        7,
        60,
        9,
        COR_SEM_LLM,
        "parser JSON com nova tentativa e reserva",
        "JsonOutputParser + with_retry (2 tentativas) + with_fallbacks (erro legível)\n"
        "interno, sem modelo de linguagem",
    )
    seta(ax, (70, 7), (70, 3), "AnaliseIncidente (INTERNA)", pos="meio", ha="left", dx=1, tam=8)
    caixa(
        ax,
        17,
        -4,
        121,
        7,
        COR_SEM_LLM,
        "7  resposta",
        "monta RespostaTurno (+ trajetoria); interno, sem modelo de linguagem",
    )
    seta(
        ax,
        (77, -4),
        (77, -8),
        "RespostaTurno  (saída; INTERNA: função)",
        pos="meio",
        ha="left",
        dx=1,
        tam=8,
    )
    legenda(
        ax,
        [
            ("componente nosso, sem modelo de linguagem", COR_SEM_LLM, None),
            ("componente nosso que chama modelo de linguagem", COR_LLM, None),
            ("serviço externo", COR_EXTERNO, None),
            ("respostas fixas e respostas gravadas (reserva)", COR_FIXA, None),
            ("seta cheia: chamada interna (função, arquivo ou classe)", None, None),
            ("seta tracejada: chamada externa (rede)", None, True),
        ],
        17,
        -12,
        60,
        ncol=2,
    )
    fig.savefig(SAIDA / "componentes_fase2.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _curto_prazo(ax):
    ax.add_patch(
        FancyBboxPatch(
            (2, 71),
            84,
            20,
            boxstyle="round,pad=0,rounding_size=0.8",
            fc="none",
            ec=COR_SISTEMA[1],
            lw=1.4,
            ls=":",
            zorder=0,
        )
    )
    ax.text(
        3, 90.2, "memória de curto prazo", fontsize=10.5, fontweight="bold", color=TXT, va="top"
    )
    caixa(
        ax,
        44,
        73,
        40,
        14,
        COR_SISTEMA,
        "Conversa (RunnableWithMessageHistory)",
        "filtro de relevância e trim_messages;\n"
        "resumo híbrido acima do limite\nSessao com session_id uuid4",
    )
    caixa(
        ax,
        4,
        73,
        28,
        14,
        COR_SISTEMA,
        "InMemoryChatMessageHistory",
        "um por session_id:\nresumo + mensagens recentes",
    )
    seta(ax, (44, 80), (32, 80), "INTERNA:\nlê e grava\no histórico", estilo="<|-|>", tam=7.5)


def _longo_prazo(ax):
    ax.add_patch(
        FancyBboxPatch(
            (2, 2),
            82,
            24,
            boxstyle="round,pad=0,rounding_size=0.8",
            fc="none",
            ec=COR_SISTEMA[1],
            lw=1.4,
            ls=":",
            zorder=0,
        )
    )
    ax.text(
        83,
        25.2,
        "memória de longo prazo: MemoriaLongoPrazo (InMemoryVectorStore)",
        ha="right",
        fontsize=10.5,
        fontweight="bold",
        color=TXT,
        va="top",
    )
    caixa(
        ax,
        5,
        4.5,
        36,
        13,
        COR_SISTEMA,
        "memória episódica",
        "Document tipo=episodica: causa confirmada\nbusca com decaimento temporal",
    )
    caixa(
        ax,
        45,
        4.5,
        36,
        13,
        COR_FASE2,
        "memória semântica (wiki)",
        "Document tipo=semantica: fato, fonte,\ndata e validade; uso na Fase 4",
        tracejada=True,
    )
    caixa(
        ax,
        100,
        15,
        32,
        10,
        COR_EXTERNO,
        "Embeddings OpenAI",
        "text-embedding-3-small\n(serviço externo)",
    )
    caixa(
        ax,
        100,
        1,
        32,
        10,
        COR_FIXA,
        "memoria_longo_prazo.json",
        "salvar() e carregar()\ndados_dummy/",
    )
    seta(ax, (84, 20), (100, 20), "EXTERNA:\ntexto e consulta", externa=True, tam=7.5)
    seta(ax, (84, 6), (100, 6), "INTERNA:\narquivo", estilo="<|-|>", tam=7.5)


def _consumidores(ax):
    caixa(
        ax,
        4,
        32,
        36,
        14,
        COR_LLM,
        "Registrador (passo 6, confirmação)",
        "só na intenção confirmar_causa\nchama gravar_episodio (com trava)\n"
        "chama modelo de linguagem (EXTERNA)",
    )
    caixa(
        ax,
        46,
        32,
        40,
        14,
        COR_LLM,
        "Investigador (agente ReAct, passo 6)",
        "ferramentas só leitura: logs, métricas,\ndeploys, GitHub e memória\n"
        "chama modelo de linguagem (EXTERNA)",
    )
    caixa(
        ax,
        96,
        32,
        32,
        14,
        COR_SISTEMA,
        "consultar_memoria",
        "ferramenta só leitura\n(servico, descricao)\nresultado marcado como histórico",
    )
    seta(ax, (50, 54), (22, 46), "INTERNA:\nconfirmar_causa", pos="meio", ha="center", tam=7.5)
    seta(
        ax,
        (66, 54),
        (66, 46),
        "INTERNA: demais\nintenções",
        pos="meio",
        ha="left",
        dx=0.6,
        tam=7.5,
    )
    seta(ax, (86, 39), (96, 39), "INTERNA:\nchamada", tam=7.5)
    seta(
        ax,
        (18, 32),
        (18, 17.5),
        "INTERNA: registrar_episodio\n(única escrita)",
        pos="meio",
        ha="right",
        dx=-0.6,
        tam=7.5,
    )
    linha(
        ax,
        [(104, 32), (104, 29), (37, 29), (37, 17.5)],
        "INTERNA: consultar_episodios (só leitura)",
        70,
        30.2,
        ha="center",
        tam=7.5,
    )


def componentes_fase3():
    fig, ax = nova_figura(26, 23, 140, 110, -14)
    ax.text(
        70,
        109.5,
        "incident-agent: componentes da Fase 3 (memória de curto e longo prazo)",
        ha="center",
        va="top",
        fontsize=15,
        fontweight="bold",
        color=TXT,
    )
    caixa(ax, 44, 94, 40, 9, COR_PESSOA, "Engenheiro de plantão", "uma sessão por incidente")
    seta(ax, (54, 94), (54, 91), "mensagem", pos="meio", ha="right", dx=-0.6, tam=7.5)
    seta(ax, (74, 91), (74, 94), "RespostaTurno", pos="meio", ha="left", dx=0.6, tam=7.5)
    _curto_prazo(ax)
    caixa(
        ax,
        100,
        54,
        28,
        37,
        COR_EXTERNO,
        "Modelo de linguagem",
        "API de chat\nOpenAI ou DeepSeek\n(serviço externo)\n\n"
        "resume a conversa,\ncompreensão, investigação\ne extração da causa",
    )
    seta(ax, (84, 80), (100, 80), "EXTERNA:\nresumo", externa=True, tam=7.5)
    caixa(
        ax,
        44,
        54,
        40,
        14,
        COR_SISTEMA,
        "Pipeline (passos 1 a 7)",
        "máscara, moderação, compreensão, roteador,\ninvestigação e resposta",
    )
    seta(
        ax,
        (54, 73),
        (54, 68),
        "{mensagem, historico,\nincidente_id}",
        pos="meio",
        ha="right",
        dx=-0.6,
        dy=-1.2,
        tam=7.5,
    )
    seta(ax, (74, 68), (74, 73), "RespostaTurno", pos="meio", ha="left", dx=0.6, tam=7.5)
    seta(ax, (84, 61), (100, 61), "EXTERNA:\ncompreensão,\nagente", externa=True, tam=7.5)
    _consumidores(ax)
    _longo_prazo(ax)
    legenda(
        ax,
        [
            ("componente nosso, sem modelo de linguagem", COR_SEM_LLM, None),
            ("componente nosso que chama modelo de linguagem", COR_LLM, None),
            ("serviço externo", COR_EXTERNO, None),
            ("arquivo de dados", COR_FIXA, None),
            ("interface pronta, uso na Fase 4 (tracejado)", COR_FASE2, True),
            ("seta cheia: chamada interna (função, arquivo ou classe)", None, None),
            ("seta tracejada: chamada externa (rede)", None, True),
        ],
        4,
        -4,
        45,
        ncol=3,
    )
    fig.savefig(SAIDA / "componentes_fase3.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def titulo(ax, x, y, texto):
    ax.text(x, y, texto, ha="center", va="top", fontsize=15, fontweight="bold", color=TXT)


def contorno(ax, x, y, w, h, rotulo):
    """Container pontilhado com rótulo no canto superior esquerdo."""
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0,rounding_size=0.8",
            fc="none",
            ec=COR_SISTEMA[1],
            lw=1.4,
            ls=":",
            zorder=0,
        )
    )
    ax.text(x + 1, y + h - 0.8, rotulo, fontsize=10.5, fontweight="bold", color=TXT, va="top")


FERRAMENTAS_FASE4 = [
    (
        "loja (incident-shop)",
        "contrato 1.1.0, API interna:\nbuscar_logs\nbuscar_metricas\nlistar_deploys\n"
        "consultar_estatisticas_banco",
        COR_SEM_LLM,
    ),
    ("GitHub", "comparar_versoes\n(API web)\ncommits, arquivos\ne trechos do diff", COR_SEM_LLM),
    (
        "documentação",
        "buscar_documentacao\nRAG (busca em documentos)\nsobre os runbooks",
        COR_SEM_LLM,
    ),
    (
        "wiki",
        "consultar_wiki: memória semântica\ncom fonte, data e validade;\n"
        "grava fato da documentação;\n"
        "senão pergunta ao engenheiro",
        COR_SEM_LLM,
    ),
    (
        "sugerir_acao",
        "ferramenta semântica:\nmodelo de linguagem\ndentro da ferramenta;\n"
        "ação sugerida, não executada",
        COR_LLM,
    ),
    (
        "memória episódica",
        "consultar_memoria\ncausas já confirmadas\nem incidentes anteriores",
        COR_SEM_LLM,
    ),
]


def _agentes_isolados(ax):
    caixa(
        ax,
        2,
        92,
        34,
        14,
        COR_LLM,
        "Agente de consulta SQL",
        "consultar_sql sobre\ndados/incidentes.db\nsó SELECT (isolado)",
    )
    caixa(
        ax,
        2,
        74,
        34,
        14,
        COR_LLM,
        "Agente de recuperação",
        "pergunta reescrita em\ntermos técnicos\n(isolado)",
    )
    seta(ax, (46, 99), (36, 99), "INTERNA:\ndelega", estilo="<|-|>", tam=7.5)
    seta(ax, (46, 90), (36, 90), "INTERNA:\ndelega", estilo="<|-|>", tam=7.5)


def _servicos_fase4(ax):
    """Faixa de serviços e dados sob cada ferramenta."""
    destinos = [
        (COR_EXTERNO, "incident-shop (LOJA_URL)", "serviço externo", True),
        (COR_EXTERNO, "GitHub API", "serviço externo", True),
        (COR_FIXA, "índice FAISS", "dados/indice_faiss\nrunbooks em\ndados/documentos", False),
        (COR_SISTEMA, "memória semântica", "fato, fonte, data\ne validade", False),
        (COR_EXTERNO, "Modelo de linguagem", "API de chat\n(serviço externo)", True),
        (COR_SISTEMA, "memória episódica", "causas confirmadas\n(episódios)", False),
    ]
    for posicao, (cor, nome, nota, externa) in enumerate(destinos):
        x0 = 4 + posicao * 22.5
        caixa(ax, x0, 26, 21, 12, cor, nome, nota)
        seta(ax, (x0 + 4, 50), (x0 + 4, 38), "", externa=externa, estilo="<|-|>")


def _registrador_fase4(ax):
    caixa(
        ax,
        4,
        4,
        44,
        12,
        COR_PESSOA,
        "Engenheiro de plantão",
        "confirma a causa ou o fato;\nresponde quando a wiki pergunta",
    )
    caixa(
        ax,
        72,
        2,
        66,
        14,
        COR_LLM,
        "Registrador (única escrita)",
        "gravar_episodio (trava: confirmar_causa) e gravar_fato (trava: confirmar_fato)\n"
        "só roda quando o engenheiro confirma; chama modelo de linguagem (EXTERNA)",
    )
    seta(ax, (48, 10), (72, 10), "confirmação", pos="acima", tam=8)
    seta(ax, (76, 16), (76, 26), "")
    seta(ax, (130, 16), (130, 26), "")


def componentes_fase4():
    fig, ax = nova_figura(27, 21, 140, 109, -14)
    titulo(ax, 70, 108.5, "incident-agent: componentes da Fase 4 (ferramentas e agentes isolados)")
    caixa(
        ax,
        46,
        86,
        52,
        16,
        COR_LLM,
        "Investigador (agente ReAct, create_agent)",
        "ciclo: raciocina, chama ferramenta, observa;\n"
        "observações mascaradas antes do modelo de linguagem\n"
        "chama modelo de linguagem (API de chat EXTERNA)",
    )
    _agentes_isolados(ax)
    contorno(ax, 2, 48, 136, 23, "ferramentas do Investigador: só leitura (nada é alterado fora)")
    for posicao, (nome, detalhe, cor) in enumerate(FERRAMENTAS_FASE4):
        caixa(ax, 4 + posicao * 22.5, 50, 21, 16, cor, nome, detalhe)
    seta(
        ax,
        (72, 86),
        (72, 71),
        "INTERNA: chama as ferramentas e recebe\nas observações (só leitura)",
        pos="meio",
        ha="left",
        dx=1,
        estilo="<|-|>",
        tam=8,
    )
    _servicos_fase4(ax)
    _registrador_fase4(ax)
    legenda(
        ax,
        [
            ("pessoa", COR_PESSOA, None),
            ("componente nosso, sem modelo de linguagem", COR_SEM_LLM, None),
            ("componente nosso que chama modelo de linguagem", COR_LLM, None),
            ("serviço externo", COR_EXTERNO, None),
            ("arquivo de dados", COR_FIXA, None),
            ("seta cheia: chamada interna (função, arquivo ou classe)", None, None),
            ("seta tracejada: chamada externa (rede)", None, True),
        ],
        4,
        -2,
        45,
        ncol=3,
    )
    fig.savefig(SAIDA / "componentes_fase4.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _barreira(ax):
    contorno(ax, 6, 59, 128, 19, "Barreira (antes de investigar)")
    passos = [
        (COR_SEM_LLM, "máscara de segredos", "regex local\nsem modelo de linguagem"),
        (COR_SEM_LLM, "moderação", "limiar por categoria;\nchama serviço externo"),
        (COR_LLM, "compreensão (NLU)", "entende a intenção;\nchama modelo de linguagem"),
        (COR_SEM_LLM, "roteador", "escolhe o caminho\npela intenção"),
    ]
    for posicao, (cor, nome, nota) in enumerate(passos):
        x0 = 10 + posicao * 31.5
        caixa(ax, x0, 60.5, 25, 12, cor, nome, nota)
        if posicao:
            seta(ax, (x0 - 6.5, 66.5), (x0, 66.5), "")


def _ramos(ax):
    caixa(
        ax,
        4,
        32,
        66,
        22,
        COR_LLM,
        "Investigador (agente ReAct)",
        "todas as ferramentas, só leitura: loja (logs, métricas, deploys,\n"
        "estatísticas do banco), GitHub, SQL (agente isolado, só SELECT),\n"
        "documentação (RAG: busca em documentos), wiki, memória\n"
        "e sugerir_acao (ação sugerida, não executada)",
    )
    caixa(
        ax,
        74,
        32,
        30,
        22,
        COR_LLM,
        "Registrador",
        "pede confirmação do\nengenheiro antes de gravar:\n"
        "gravar_episodio (causa)\ne gravar_fato (wiki)",
    )
    caixa(
        ax,
        108,
        32,
        30,
        22,
        COR_SEM_LLM,
        "Post-mortem",
        "template em código gera o .md;\núnico atuador do sistema,\nsó a pedido do engenheiro",
    )
    for x, rot in [
        (37, "demais intenções"),
        (89, "confirmar causa\nou fato"),
        (123, "pedido de\npost-mortem"),
    ]:
        seta(ax, (x, 59), (x, 54), rot, pos="meio", ha="left", dx=0.8, tam=7.5)


def _auditor(ax):
    contorno(
        ax,
        6,
        7,
        128,
        20,
        "Auditor (confere as análises do Investigador; confirmação e post-mortem vão direto à "
        "resposta)",
    )
    passos = [
        (
            COR_LLM,
            "extração de afirmações",
            "separa o que a resposta\nafirma (modelo de linguagem)",
        ),
        (COR_SEM_LLM, "checagem determinística", "confere cada afirmação\ncontra as observações"),
        (COR_LLM, "coerência e falácias", "procura contradições e\nraciocínios falhos (modelo)"),
    ]
    for posicao, (cor, nome, nota) in enumerate(passos):
        x0 = 10 + posicao * 41
        caixa(ax, x0, 8.5, 36, 12, cor, nome, nota)
        if posicao:
            seta(ax, (x0 - 5, 14.5), (x0, 14.5), "")
    seta(ax, (37, 32), (37, 27), "análise", pos="meio", ha="left", dx=0.8, tam=7.5)


def arquitetura_final():
    fig, ax = nova_figura(22, 29, 140, 136, -46)
    titulo(ax, 70, 135.5, "incident-agent: arquitetura final (fluxo de um turno)")
    caixa(ax, 50, 118, 40, 8, COR_PESSOA, "Engenheiro de plantão", "uma sessão por incidente")
    caixa(
        ax,
        40,
        101,
        60,
        10,
        COR_SISTEMA,
        "Interface web (FastAPI + HTML/CSS/JS)",
        "chat de uso (conversa) e painel de análise (registro dos turnos)",
    )
    caixa(
        ax,
        40,
        83,
        60,
        12,
        COR_SISTEMA,
        "Sessão (RunnableWithMessageHistory)",
        "um histórico por session_id;\nfiltro de relevância, janela e resumo",
    )
    seta(ax, (70, 118), (70, 111), "mensagem", pos="meio", ha="left", dx=1, tam=8)
    seta(ax, (70, 101), (70, 95), "", pos="meio")
    seta(ax, (70, 83), (70, 78), "pergunta + histórico", pos="meio", ha="left", dx=1, tam=8)
    _barreira(ax)
    _ramos(ax)
    _auditor(ax)
    caixa(
        ax,
        30,
        -8,
        80,
        10,
        COR_SISTEMA,
        "Resposta",
        "entregue ao engenheiro; com aviso destacado se o Auditor reprovar",
    )
    seta(ax, (70, 7), (70, 2), "")
    caixa(
        ax,
        6,
        -30,
        62,
        14,
        COR_SISTEMA,
        "Registro de turnos",
        "guarda cada turno (pergunta, ferramentas, veredito);\n"
        "alimenta o painel de análise da interface web",
    )
    caixa(
        ax,
        72,
        -30,
        62,
        14,
        COR_EXTERNO,
        "Avaliação no LangSmith",
        "dataset dos 8 cenários;\ncausa certa, trajetória e auditor",
    )
    seta(ax, (40, -8), (40, -16), "INTERNA: grava", pos="meio", ha="left", dx=1, tam=8)
    seta(
        ax,
        (100, -8),
        (100, -16),
        "EXTERNA: execuções",
        externa=True,
        pos="meio",
        ha="left",
        dx=1,
        tam=8,
    )
    legenda(
        ax,
        [
            ("pessoa", COR_PESSOA, None),
            ("componente nosso, sem modelo de linguagem", COR_SEM_LLM, None),
            ("componente nosso que chama modelo de linguagem", COR_LLM, None),
            ("serviço externo", COR_EXTERNO, None),
            ("seta cheia: chamada interna", None, None),
            ("seta tracejada: chamada externa (rede)", None, True),
        ],
        6,
        -36,
        65,
        ncol=2,
    )
    fig.savefig(SAIDA / "arquitetura_final.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    SAIDA.mkdir(parents=True, exist_ok=True)
    contexto()
    componentes()
    componentes_fase2()
    componentes_fase3()
    componentes_fase4()
    arquitetura_final()
    print(
        "gerados:",
        SAIDA / "contexto.png",
        SAIDA / "componentes.png",
        SAIDA / "componentes_fase2.png",
        SAIDA / "componentes_fase3.png",
        SAIDA / "componentes_fase4.png",
        SAIDA / "arquitetura_final.png",
    )
