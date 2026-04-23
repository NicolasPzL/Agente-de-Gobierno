"""Entrypoint de linea de comandos del Sprint 1.

Uso:
    python -m ate "¿Que contratos tiene el candidato X en SECOP?"

Ejecuta el grafo hasta el planificador y emite el plan (intencion +
tools seleccionadas + razonamiento) como JSON en stdout.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import List, Optional

from ate.graph.builder import construir_grafo
from ate.schemas.state import EstadoGrafo


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ate",
        description=(
            "Agente de Transparencia Electoral - Sprint 1. "
            "Recibe una pregunta y emite el plan (intencion + tools) en JSON."
        ),
    )
    parser.add_argument(
        "pregunta",
        help='Pregunta del usuario, entre comillas. Ej: "¿Que contratos tiene X?"',
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Muestra logs de debug del grafo y del planificador.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    grafo = construir_grafo()
    estado_inicial: EstadoGrafo = {"pregunta": args.pregunta}
    estado_final = grafo.invoke(estado_inicial)

    plan = estado_final.get("plan")
    if plan is None:
        print("Error: el grafo termino sin producir un plan.", file=sys.stderr)
        return 2

    salida = {
        "pregunta": args.pregunta,
        "plan": plan.model_dump(mode="json"),
    }
    print(json.dumps(salida, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
