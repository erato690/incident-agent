"""Máscara local de segredos e dados pessoais (sem LLM)."""
import re

_PADROES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bBearer\s+[\w.\-~+/]+=*", re.I), "Bearer [SEGREDO]"),
    (re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+"), "[SEGREDO]"),
    (re.compile(r"\bsk-[\w-]{16,}"), "[SEGREDO]"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}"), "[SEGREDO]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[SEGREDO]"),
    (re.compile(r"\b(senha|password|pwd|secret|token|api[_-]?key)(\s*[=:]\s*)(?!\[SEGREDO\])\S+", re.I),
     r"\1\2[SEGREDO]"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
]
_CARTAO = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


def _luhn(digitos: str) -> bool:
    soma = 0
    for i, d in enumerate(reversed(digitos)):
        n = int(d) * (2 if i % 2 else 1)
        soma += n - 9 if n > 9 else n
    return soma % 10 == 0


def _troca_cartao(m: re.Match) -> str:
    return "[CARTAO]" if _luhn(re.sub(r"\D", "", m.group())) else m.group()


def mascarar(texto: str) -> str:
    """Troca segredos e PII por marcadores; idempotente."""
    for padrao, troca in _PADROES:
        texto = padrao.sub(troca, texto)
    return _CARTAO.sub(_troca_cartao, texto)
