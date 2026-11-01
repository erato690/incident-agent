import sys
from pathlib import Path

# Coloca a raiz do repositório no sys.path para importar `agente`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
