"""Gera o PDF do relatório técnico a partir de docs/relatorio.md.

Uso: .venv/bin/python scripts/gerar_relatorio_pdf.py
"""

import re
import sys
from pathlib import Path

import markdown
from xhtml2pdf import pisa

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "docs" / "relatorio.md"
SAIDA = RAIZ / "docs" / "rafael_dias_ai-agents_langchain-agents.pdf"
LARGURA_IMAGEM = 440

ESTILO = """
@page { size: A4; margin: 2.2cm 2cm 2.2cm 2cm;
  @frame rodape { -pdf-frame-content: rodape; bottom: 0.8cm; left: 2cm; right: 2cm;
    height: 0.6cm; } }
body { font-family: Helvetica; font-size: 10pt; line-height: 1.35; color: #1a1a1a; }
h1 { font-size: 22pt; color: #12355b; margin-top: 150pt; margin-bottom: 8pt; }
h2 { font-size: 14pt; color: #12355b; margin-top: 16pt; border-bottom: 1px solid #12355b; }
h3 { font-size: 11.5pt; color: #1f4e79; margin-top: 12pt; }
p { margin: 4pt 0; text-align: left; }
li { margin-bottom: 2pt; }
table { width: 100%; border-collapse: collapse; margin: 6pt 0; }
th { background-color: #e3ebf5; font-weight: bold; text-align: left; }
th, td { border: 0.5px solid #8a99ad; padding: 3pt 4pt; font-size: 8.5pt; vertical-align: top; }
code { font-family: Courier; font-size: 8.5pt; background-color: #f1f1f1; }
img { margin: 4pt 0; }
em { color: #444444; }
.pendente { background-color: #fff176; font-weight: bold; }
"""

MODELO = (
    '<html><head><meta charset="utf-8"><style>{estilo}</style></head><body>'
    '<div id="rodape" style="text-align:center; font-size:8pt; color:#666;">'
    "Agente investigador de incidentes de produção - Rafael Dias - página <pdf:pagenumber/>"
    "</div>{corpo}</body></html>"
)


def converter_markdown(texto: str) -> str:
    html = markdown.markdown(texto, extensions=["tables", "sane_lists"])
    html = html.replace('<div class="quebra"></div>', "<pdf:nextpage />")
    html = re.sub(
        r"(\[\[PREENCHER[^\]]*(?:\][^\]][^\]]*)*\]\])", r'<span class="pendente">\1</span>', html
    )
    return re.sub(r"<img ([^>]*?)/?>", rf'<img \1 width="{LARGURA_IMAGEM}" />', html)


def resolver_caminho(uri: str, *_args: object) -> str:
    caminho = Path(uri)
    return str(caminho if caminho.is_absolute() else ENTRADA.parent / uri)


def gerar() -> int:
    corpo = converter_markdown(ENTRADA.read_text(encoding="utf-8"))
    html = MODELO.format(estilo=ESTILO, corpo=corpo)
    with SAIDA.open("wb") as arquivo:
        resultado = pisa.CreatePDF(html, dest=arquivo, link_callback=resolver_caminho)
    print(f"PDF gerado em {SAIDA}" if not resultado.err else "Erro ao gerar o PDF")
    return int(bool(resultado.err))


if __name__ == "__main__":
    sys.exit(gerar())
