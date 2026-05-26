"""Entrypoint de linea de comandos.

Uso:
    python -m ate "¿Que contratos tiene el candidato X en SECOP?"

Sprint 1: emitia solo el plan del planificador.
Sprint 2: tambien emite el `contexto_extraido` con los resultados de
las tools invocadas. Ambos campos viven bajo el JSON final, asi cualquier
script externo puede pipear la salida (`python -m ate "..." | jq ...`).
Sprint 4: tambien emite `contraste` (inconsistencias propuesta vs datos)
y `validacion` (verificacion de dominios de fuentes oficiales).
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
            "Agente de Transparencia Electoral. Recibe una pregunta y emite "
            "el plan + el contexto extraido en JSON."
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
        help="Muestra logs de debug del grafo, planificador y extractor.",
    )
    parser.add_argument(
        "--solo-plan",
        action="store_true",
        help="Emite solo el plan (omite el contexto extraido). Util para pruebas rapidas.",
    )
    parser.add_argument(
        "--resumen",
        action="store_true",
        help=(
            "En lugar de los resultados crudos, emite un resumen por tool "
            "(fuente, estado, total, urls)."
        ),
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

    salida: dict = {
        "pregunta": args.pregunta,
        "plan": plan.model_dump(mode="json"),
    }

    contexto = estado_final.get("contexto_extraido")
    if contexto is not None and not args.solo_plan:
        if args.resumen:
            salida["contexto_extraido"] = {
                "consulta": contexto.consulta,
                "tools_invocadas": contexto.tools_invocadas,
                "tools_omitidas": contexto.tools_omitidas,
                "resultados": [
                    {
                        "tool": r.tool,
                        "fuente": r.fuente,
                        "estado": r.estado,
                        "total_resultados": r.total_resultados,
                        "urls_oficiales": r.urls_oficiales,
                        "mensaje": r.mensaje,
                    }
                    for r in contexto.resultados
                ],
            }
        else:
            salida["contexto_extraido"] = contexto.model_dump(mode="json")

    contexto_rag = estado_final.get("contexto_rag")
    if contexto_rag is not None and not args.solo_plan:
        if args.resumen:
            salida["contexto_rag"] = {
                "consulta": contexto_rag.consulta,
                "candidato_filtro": contexto_rag.candidato_filtro,
                "estado": contexto_rag.estado,
                "mensaje": contexto_rag.mensaje,
                "pasajes": [
                    {
                        "candidato": p.candidato_nombre,
                        "pdf": p.pdf,
                        "pagina": p.pagina,
                        "score": round(p.score, 4),
                        "fragmento": p.texto[:200] + ("…" if len(p.texto) > 200 else ""),
                    }
                    for p in contexto_rag.pasajes
                ],
            }
        else:
            salida["contexto_rag"] = contexto_rag.model_dump(mode="json")

    # --- Sprint 4: contraste ---
    contraste = estado_final.get("contraste")
    if contraste is not None and not args.solo_plan:
        if args.resumen:
            salida["contraste"] = {
                "candidato_id": contraste.candidato_id,
                "estado": contraste.estado,
                "mensaje": contraste.mensaje,
                "n_propuestas": contraste.n_propuestas_analizadas,
                "n_contratos": contraste.n_contratos_analizados,
                "n_sanciones": contraste.n_sanciones_analizadas,
                "inconsistencias": [
                    {
                        "tipo": i.tipo,
                        "descripcion": i.descripcion,
                        "fuentes": i.fuentes,
                    }
                    for i in contraste.inconsistencias
                ],
            }
        else:
            salida["contraste"] = contraste.model_dump(mode="json")

    # --- Sprint 4: validacion ---
    validacion = estado_final.get("validacion")
    if validacion is not None and not args.solo_plan:
        if args.resumen:
            salida["validacion"] = {
                "estado": validacion.estado,
                "mensaje": validacion.mensaje,
                "total_fuentes": validacion.total_fuentes,
                "fuentes_oficiales": validacion.fuentes_oficiales,
                "fuentes_no_oficiales": validacion.fuentes_no_oficiales,
                "fuentes_inaccesibles": validacion.fuentes_inaccesibles,
                "fuentes": [
                    {
                        "url": f.url,
                        "es_oficial": f.es_oficial,
                        "accesible": f.accesible,
                        "dominio": f.dominio_detectado,
                    }
                    for f in validacion.fuentes_validadas
                ],
            }
        else:
            salida["validacion"] = validacion.model_dump(mode="json")

    print(json.dumps(salida, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
