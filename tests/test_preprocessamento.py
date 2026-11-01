from agente.preprocessamento import preprocessar

TRACE = "\n".join(
    ["java.lang.NullPointerException: Cannot invoke \"Cupom.getDesconto()\" because \"cupom\" is null"]
    + ["\tat java.base/java.util.HashMap.get(HashMap.java:100)",
       "\tat sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method)"] * 30
    + ["\tat org.springframework.web.servlet.FrameworkServlet.service(FrameworkServlet.java:1)"] * 30
    + ["\tat br.loja.pagamentos.PagamentoService.confirmar(PagamentoService.java:88)",
       "\tat br.loja.pagamentos.PagamentoController.post(PagamentoController.java:41)",
       "Caused by: java.sql.SQLException: conexao perdida",
       "\tat java.base/java.net.Socket.read(Socket.java:5)"]
)


def test_remove_frames_de_biblioteca_e_mantem_essencial():
    r = preprocessar(TRACE)
    t = r.texto_limpo
    assert "java.lang.NullPointerException" in t
    assert "PagamentoService.confirmar(PagamentoService.java:88)" in t
    assert "PagamentoController.post" not in t  # só o primeiro frame da aplicação
    assert "Caused by: java.sql.SQLException" in t
    assert "HashMap" not in t and "springframework" not in t and "NativeMethod" not in t


def test_corta_em_4000_caracteres():
    r = preprocessar("erro " + "x" * 10_000)
    assert len(r.texto_limpo) == 4000


def test_impressao_digital():
    r = preprocessar("NullPointerException em PagamentoService.java:88 no pagamentos-api")
    assert r.impressao.excecao == "NullPointerException"
    assert r.impressao.servico == "pagamentos-api"


def test_impressao_digital_do_trace():
    i = preprocessar(TRACE).impressao
    assert i.excecao == "NullPointerException"
    assert "PagamentoService.java:88" in i.primeiro_frame


def test_servico_do_parametro_tem_prioridade():
    assert preprocessar("auth-api caiu", servico="pedidos-api").impressao.servico == "pedidos-api"


def test_servico_detectado_no_texto():
    for s in ("pedidos-api", "pagamentos-api", "estoque-worker", "auth-api"):
        assert preprocessar(f"problema no {s} agora").impressao.servico == s


def test_texto_sem_erro_mantem_vazio_os_campos():
    i = preprocessar("clientes não conseguem pagar").impressao
    assert i.excecao is None and i.primeiro_frame is None and i.servico is None


def test_traceback_python_sem_site_packages():
    t = ('Traceback (most recent call last):\n'
         '  File "/usr/lib/site-packages/x.py", line 1, in f\n    lib()\n'
         '  File "/app/worker/config.py", line 12, in <module>\n    QUEUE = os.environ["Q"]\n'
         "KeyError: 'Q'")
    r = preprocessar(t)
    assert "site-packages" not in r.texto_limpo and "lib()" not in r.texto_limpo
    assert r.impressao.excecao == "KeyError"
    assert "/app/worker/config.py" in r.impressao.primeiro_frame
