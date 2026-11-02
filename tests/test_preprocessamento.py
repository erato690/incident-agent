from agente.preprocessamento import preprocessar

TRACE = "\n".join(
    ['java.lang.NullPointerException: Cannot invoke "Cupom.getDesconto()" because "cupom" is null']
    + [
        "\tat java.base/java.util.HashMap.get(HashMap.java:100)",
        "\tat sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method)",
    ]
    * 30
    + ["\tat org.springframework.web.servlet.FrameworkServlet.service(FrameworkServlet.java:1)"]
    * 30
    + [
        "\tat br.loja.pagamentos.PagamentoService.confirmar(PagamentoService.java:88)",
        "\tat br.loja.pagamentos.PagamentoController.post(PagamentoController.java:41)",
        "Caused by: java.sql.SQLException: conexao perdida",
        "\tat java.base/java.net.Socket.read(Socket.java:5)",
    ]
)


def test_remove_frames_de_biblioteca_e_mantem_essencial():
    erro = preprocessar(TRACE)
    texto_limpo = erro.texto_limpo
    assert "java.lang.NullPointerException" in texto_limpo
    assert "PagamentoService.confirmar(PagamentoService.java:88)" in texto_limpo
    assert "PagamentoController.post" not in texto_limpo  # só o primeiro frame da aplicação
    assert "Caused by: java.sql.SQLException" in texto_limpo
    assert (
        "HashMap" not in texto_limpo
        and "springframework" not in texto_limpo
        and "NativeMethod" not in texto_limpo
    )


def test_corta_em_4000_caracteres():
    erro = preprocessar("erro " + "x" * 10_000)
    assert len(erro.texto_limpo) == 4000


def test_impressao_digital():
    erro = preprocessar("NullPointerException em PagamentoService.java:88 no pagamentos-api")
    assert erro.impressao.excecao == "NullPointerException"
    assert erro.impressao.servico == "pagamentos-api"


def test_impressao_digital_do_trace():
    impressao = preprocessar(TRACE).impressao
    assert impressao.excecao == "NullPointerException"
    assert "PagamentoService.java:88" in impressao.primeiro_frame


def test_servico_do_parametro_tem_prioridade():
    assert preprocessar("auth-api caiu", servico="pedidos-api").impressao.servico == "pedidos-api"


def test_servico_detectado_no_texto():
    for servico in ("pedidos-api", "pagamentos-api", "estoque-worker", "auth-api"):
        assert preprocessar(f"problema no {servico} agora").impressao.servico == servico


def test_texto_sem_erro_mantem_vazio_os_campos():
    impressao = preprocessar("clientes não conseguem pagar").impressao
    assert (
        impressao.excecao is None and impressao.primeiro_frame is None and impressao.servico is None
    )


def test_traceback_python_sem_site_packages():
    texto_limpo = (
        "Traceback (most recent call last):\n"
        '  File "/usr/lib/site-packages/x.py", line 1, in f\n    lib()\n'
        '  File "/app/worker/config.py", line 12, in <module>\n    QUEUE = os.environ["Q"]\n'
        "KeyError: 'Q'"
    )
    erro = preprocessar(texto_limpo)
    assert "site-packages" not in erro.texto_limpo and "lib()" not in erro.texto_limpo
    assert erro.impressao.excecao == "KeyError"
    assert "/app/worker/config.py" in erro.impressao.primeiro_frame
