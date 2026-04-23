"""Genera los artefactos del grafo base (entregable del Sprint 1).

Usa `grafo.get_graph()` — el introspector nativo de LangGraph — para
producir tres archivos en `docs/`:

    grafo_sprint1.mmd  (Mermaid, texto plano - ideal para README / MD)
    grafo_sprint1.png  (imagen generada via mermaid.ink; requiere red)
    grafo_sprint1.txt  (ASCII art para pegar en la consola)

Uso:
    python scripts/generar_grafo.py

El PNG puede fallar si no hay internet (mermaid.ink es el renderer por
defecto). En ese caso el script no revienta: deja el .mmd y el .txt,
que son suficientes para el entregable.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ate.graph.builder import construir_grafo  # noqa: E402


def main() -> int:
    docs = _ROOT / "docs"
    docs.mkdir(exist_ok=True)

    grafo = construir_grafo()
    introspector = grafo.get_graph()

    # 1. Mermaid (texto) - entregable principal, cero dependencias.
    ruta_mmd = docs / "grafo_sprint1.mmd"
    ruta_mmd.write_text(introspector.draw_mermaid(), encoding="utf-8")
    print(f"[ok] Mermaid -> {ruta_mmd.relative_to(_ROOT)}")

    # 2. ASCII - util para logs / terminal.
    ruta_txt = docs / "grafo_sprint1.txt"
    try:
        ascii_art = introspector.draw_ascii()
        ruta_txt.write_text(ascii_art, encoding="utf-8")
        print(f"[ok] ASCII   -> {ruta_txt.relative_to(_ROOT)}")
    except (ImportError, Exception) as exc:  # grandalf opcional
        print(f"[skip] ASCII: {exc.__class__.__name__}: {exc}")

    # 3. PNG - entregable visual. Requiere red (mermaid.ink).
    ruta_png = docs / "grafo_sprint1.png"
    try:
        png_bytes = introspector.draw_mermaid_png()
        ruta_png.write_bytes(png_bytes)
        print(f"[ok] PNG     -> {ruta_png.relative_to(_ROOT)}")
    except Exception as exc:
        print(
            f"[skip] PNG: {exc.__class__.__name__}: {exc} "
            "(requiere conexion a mermaid.ink; el .mmd sirve igual)"
        )

    # 4. Eco del Mermaid a stdout para copiar/pegar rapido.
    print("\n--- Mermaid generado ---")
    print(introspector.draw_mermaid())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
