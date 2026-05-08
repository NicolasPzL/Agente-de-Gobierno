"""Configuracion de pytest.

Responsabilidades:
    1. Garantiza que `src/` este en el sys.path (red de seguridad si el
       paquete no se instalo en editable).
    2. Fuerza variables de entorno seguras ANTES de cualquier import del
       paquete:
        - `ATE_LLM_PROVIDER=none` -> el planificador no toca el LLM.
        - `ATE_OFFLINE=1` -> las tools no tocan la red (failsafe ante
          cualquier monkeypatch incompleto).
       Ningun test del repo debe tocar la red ni gastar tokens.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 1. Aislar los tests del `.env` del usuario: el camino determinista y
#    el modo offline son los unicos permitidos en la suite. `os.environ`
#    tiene prioridad sobre `.env` porque `python-dotenv` por defecto no
#    sobreescribe valores ya exportados.
os.environ["ATE_LLM_PROVIDER"] = "none"
os.environ["ATE_OFFLINE"] = "1"
# Defaults explicitos para que `load_settings` siempre tenga valores
# coherentes incluso si el usuario tiene un `.env` raro.
os.environ.setdefault("ATE_NEWS_PROVIDER", "tavily")
os.environ.setdefault("ATE_MAX_RESULTADOS", "25")
os.environ.setdefault("ATE_HTTP_TIMEOUT", "5")
# RAG: dirigir la persistencia a un tmp aislado por sesion de pytest
# para que no se mezcle con la base real del usuario en `data/rag`.
import tempfile as _tmp
os.environ.setdefault("ATE_RAG_DIR", _tmp.mkdtemp(prefix="ate-rag-test-"))

# 2. Hacer importable `src/ate` sin requerir `pip install -e .`.
_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
