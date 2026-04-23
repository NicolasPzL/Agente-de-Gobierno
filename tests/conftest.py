"""Configuracion de pytest.

Responsabilidades:
    1. Garantiza que `src/` este en el sys.path (red de seguridad si el
       paquete no se instalo en editable).
    2. Fuerza `ATE_LLM_PROVIDER=none` ANTES de cualquier import del
       paquete, para que los tests que invocan el grafo no peguen a
       Ollama / Anthropic aunque exista un `.env` con otro proveedor.
       Ningun test de Sprint 1 debe tocar la red.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 1. Aislar los tests del `.env` del usuario: el camino determinista es
#    el unico permitido en la suite. `os.environ` tiene prioridad sobre
#    `.env` porque `python-dotenv` por defecto no sobreescribe valores
#    ya exportados.
os.environ["ATE_LLM_PROVIDER"] = "none"

# 2. Hacer importable `src/ate` sin requerir `pip install -e .`.
_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
