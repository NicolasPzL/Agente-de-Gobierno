#!/usr/bin/env python
"""Script de ingesta de planes de gobierno al vector store.

Uso:
    python scripts/ingestar_planes.py             # ingesta los 13 candidatos
    python scripts/ingestar_planes.py --solo ivan-cepeda
    python scripts/ingestar_planes.py --reset     # borra la coleccion antes

Requiere:
    pip install -e ".[dev]"   # trae pypdf y chromadb

La primera ejecucion baja el modelo `all-MiniLM-L6-v2` ONNX (~80MB) al
cache de HuggingFace. Las siguientes son completamente offline.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Permitir ejecutar este script directamente sin instalar el paquete.
_REPO = Path(__file__).resolve().parent.parent
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ate.candidatos.registro import CANDIDATOS_2026, por_id  # noqa: E402
from ate.rag.cliente import abrir_cliente  # noqa: E402
from ate.rag.ingestor import ingestar_candidato, ingestar_todos  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ingestar_planes",
        description="Ingesta los PDFs de planes de gobierno a ChromaDB.",
    )
    parser.add_argument(
        "--solo",
        metavar="CANDIDATO_ID",
        help=(
            "ID del candidato a ingerir (kebab-case). Si se omite, se ingieren "
            "todos los candidatos del registro."
        ),
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Borra los chunks existentes del candidato antes de ingerir.",
    )
    parser.add_argument(
        "--rag-dir",
        help="Directorio raiz de persistencia. Por defecto lee ATE_RAG_DIR o usa data/rag.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Logs DEBUG.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    cliente = abrir_cliente(args.rag_dir)

    if args.solo:
        cand = por_id(args.solo)
        if cand is None:
            ids_disp = ", ".join(c.id for c in CANDIDATOS_2026)
            print(
                f"ERROR: candidato '{args.solo}' no esta en el registro.\n"
                f"IDs disponibles: {ids_disp}",
                file=sys.stderr,
            )
            return 2
        if args.reset:
            borrados = cliente.borrar_por_candidato(cand.id)
            print(f"Borrados {borrados} chunks previos de {cand.id}.")
        n = ingestar_candidato(cand, cliente=cliente, repo_root=_REPO)
        print(f"OK: {n} chunks ingestados para {cand.id} ({cand.nombre_corto}).")
        print(f"    Total en coleccion: {cliente.contar()} chunks.")
        return 0

    # Ingesta completa.
    if args.reset:
        # Reset por candidato (preserva metadata de coleccion).
        for c in CANDIDATOS_2026:
            cliente.borrar_por_candidato(c.id)
        print("Reset completado: chunks de todos los candidatos borrados.")

    print(f"Ingestando {len(CANDIDATOS_2026)} candidatos en {cliente.ruta} ...")
    resumen = ingestar_todos(cliente=cliente, repo_root=_REPO)
    print()
    print(f"{'CANDIDATO':40} CHUNKS")
    print("-" * 50)
    for cid, n in resumen.items():
        print(f"{cid:40} {n}")
    print(f"\nTotal en coleccion: {cliente.contar()} chunks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
