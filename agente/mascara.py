"""Máscara local de segredos e dados pessoais (sem LLM)."""

import re

_PADROES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bBearer\s+[\w.\-~+/]+=*", re.I), "Bearer [SEGREDO]"),
    (re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+"), "[SEGREDO]"),
    (re.compile(r"\bsk-[\w-]{16,}"), "[SEGREDO]"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}"), "[SEGREDO]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[SEGREDO]"),
    # O valor para em espaço, aspas, parênteses, vírgula, ponto e vírgula ou ponto final
    # (ponto seguido de separador ou fim); pontos internos (ex.: "k-1.2.3") fazem parte do valor.
    (
        re.compile(
            r"\b(senha|password|pwd|secret|token|api[_-]?key)(\s*[=:]\s*)([\"']?)(?!\[SEGREDO\])"
            r"[^\s\"'(),;]+?(?=\.?(?:[\s\"'(),;]|$))",
            re.I,
        ),
        r"\1\2\3[SEGREDO]",
    ),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
]
_CARTAO = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


def _luhn(digitos: str) -> bool:
    soma = 0
    for posicao, digito in enumerate(reversed(digitos)):
        valor = int(digito) * (2 if posicao % 2 else 1)
        soma += valor - 9 if valor > 9 else valor
    return soma % 10 == 0


def _trocar_cartao(trecho: re.Match) -> str:
    numero = trecho.group()
    return "[CARTAO]" if _luhn(re.sub(r"\D", "", numero)) else numero


def mascarar(texto: str) -> str:
    """Troca segredos e PII por marcadores; idempotente."""
    for padrao, troca in _PADROES:
        texto = padrao.sub(troca, texto)
    return _CARTAO.sub(_trocar_cartao, texto)
