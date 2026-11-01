import pytest

from agente.mascara import mascarar

SEGREDOS = [
    ("senha: hunter2abc", "hunter2abc"),
    ("password=Sup3rS3cret", "Sup3rS3cret"),
    ("token: abc123def456", "abc123def456"),
    ("api_key=zzTOPsecret99", "zzTOPsecret99"),
    ("Authorization: Bearer xyz.abc-123", "xyz.abc-123"),
    ("chave sk-abcdefghijklmnopqrstuvwx", "sk-abcdefghijklmnopqrstuvwx"),
    ("gh ghp_abcdefghijklmnopqrstuvwxyz0123456789", "ghp_abcdefghijklmnopqrstuvwxyz0123456789"),
    ("aws AKIAIOSFODNN7EXAMPLE", "AKIAIOSFODNN7EXAMPLE"),
    ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.abcDEF123_-", "eyJhbGciOiJIUzI1NiJ9"),
]


@pytest.mark.parametrize("entrada,valor", SEGREDOS)
def test_segredos_viram_marcador(entrada, valor):
    saida = mascarar(entrada)
    assert valor not in saida
    assert "[SEGREDO]" in saida


def test_email():
    s = mascarar("fale com ana.souza@loja.com.br agora")
    assert "ana.souza" not in s and "[EMAIL]" in s


@pytest.mark.parametrize("cpf", ["123.456.789-09", "12345678909"])
def test_cpf(cpf):
    s = mascarar(f"cpf {cpf} ok")
    assert cpf not in s and "[CPF]" in s


@pytest.mark.parametrize("cartao", ["4111111111111111", "4111 1111 1111 1111", "4111-1111-1111-1111"])
def test_cartao(cartao):
    s = mascarar(f"cartao {cartao} fim")
    assert "4111" not in s and "[CARTAO]" in s


@pytest.mark.parametrize("texto", [
    "container levou OOMKilled",
    "HikariPool-1 - Connection is not available",
    "at PagamentoService.java:88",
    "deploy v2.14.0 do pagamentos-api",
    "KeyError: 'ESTOQUE_QUEUE_URL'",
])
def test_texto_tecnico_intacto(texto):
    assert mascarar(texto) == texto


def test_idempotente():
    t = "senha=abc12345 e ana@x.com cpf 123.456.789-09 cartao 4111 1111 1111 1111"
    assert mascarar(mascarar(t)) == mascarar(t)


def test_epoch_ms_nao_vira_cartao():
    assert mascarar("ts 1730419200000 no log") == "ts 1730419200000 no log"


def test_cartao_so_com_luhn_valido():
    assert "[CARTAO]" in mascarar("4111 1111 1111 1111")
    assert "[CARTAO]" not in mascarar("4111 1111 1111 1112")
