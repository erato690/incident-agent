import sys
from pathlib import Path

# Coloca a raiz do repositório no sys.path para importar `agente`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from agente.memoria import MemoriaLongoPrazo  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "limiar_real: usa o limiar de similaridade real (D8)")


@pytest.fixture(autouse=True)
def _sem_limiar_de_similaridade(request, monkeypatch):
    """Os embeddings falsos não têm semântica: sem o limiar D8, salvo nos testes `limiar_real`."""
    if request.node.get_closest_marker("limiar_real") is None:
        monkeypatch.setattr(MemoriaLongoPrazo.consultar_episodios, "__defaults__", (3, 0.0))
