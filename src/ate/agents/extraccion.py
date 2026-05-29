"""Agente de extraccion - Sprint 2 (refinado en Sprint 2.5).

Responsabilidades:
    1. Leer `plan: PlanEjecucion` y `pregunta: str` del estado.
    2. Reescribir la consulta por tool segun el candidato detectado
       (Sprint 2.5):
           - SECOP / datos.gov.co -> nombre canonico
           - CNE                  -> partido / movimiento
           - Buscador noticias    -> nombre + partido
       Si el plan no detecto candidato, se pasa la pregunta cruda
       (comportamiento Sprint 2).
    3. Para cada tool del plan, invocarla con la consulta apropiada y
       las settings activas, recolectando un `ResultadoExtraccion`.
    4. Empaquetar todo en un `ContextoExtraido` y devolverlo en el
       estado bajo la clave `contexto_extraido`.

Decisiones de diseno:
    - **El extractor no clasifica**: el planificador ya decidio. Si el
      plan llega vacio (intencion=indefinida), no se invoca nada y el
      contexto sale vacio.
    - **Tools que pertenecen a sprints futuros se omiten**: la tool de
      RAG (`buscar_plan_gobierno`) NO se invoca aqui — corresponde al
      agente RAG en su nodo dedicado del grafo (Sprint 3).
    - **Tolerancia a fallos**: una tool que crashea no tumba al
      extractor. Se traduce a `ResultadoExtraccion(estado="error_*")`.
    - **No se inventan datos**: el extractor solo agrega lo que las
      tools devuelven.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from ate.candidatos.modelo import Candidato
from ate.config.settings import Settings, load_settings
from ate.schemas.state import (
    ContextoExtraido,
    EstadoGrafo,
    Intencion,
    PlanEjecucion,
    ResultadoExtraccion,
)
from ate.tools import obtener
from ate.tools.registry import ToolSpec

logger = logging.getLogger(__name__)


# Tools que NO se invocan desde el extractor — pertenecen a otros agentes.
_TOOLS_DELEGADAS = frozenset({"buscar_plan_gobierno"})  # Sprint 3 -> agente RAG


def consulta_para_tool(
    pregunta: str,
    candidato: Candidato | None,
    nombre_tool: str,
) -> str:
    """Decide el termino de busqueda optimo para cada tool.

    Si hay candidato detectado, cada backend recibe la forma que mejor
    indexa esa fuente. Si no, se pasa la pregunta cruda y la tool hace
    full-text generico (comportamiento Sprint 2).
    """
    if candidato is None:
        return pregunta

    if nombre_tool == "consultar_secop":
        return candidato.consulta_secop
    if nombre_tool == "consultar_datos_abiertos":
        return candidato.consulta_datos_oficiales
    if nombre_tool == "consultar_cne":
        return candidato.consulta_cne
    if nombre_tool == "buscar_noticias":
        return _consulta_noticias(pregunta, candidato)
    # Default: pregunta cruda. Aplica a tools desconocidas o al RAG
    # (que se invoca via agente dedicado, no aqui).
    return pregunta


def _consulta_noticias(pregunta: str, candidato: Candidato) -> str:
    """Construye la consulta de noticias preservando el TEMA de la pregunta.

    A diferencia de SECOP/CNE (que indexan por nombre/partido), una busqueda
    web rinde mejor con el tema concreto que pregunta el usuario (p.ej.
    'polemica', 'escandalo', 'declaracion sobre X'). Por eso NO se reemplaza
    la pregunta por 'nombre + partido' (eso borraba el tema y devolvia
    noticias genericas). En su lugar se ancla el nombre del candidato y se
    conserva la pregunta. Si la pregunta ya menciona al candidato por su
    nombre corto, se usa tal cual para no duplicar.
    """
    tema = pregunta.strip().strip("¿?¡!").strip()
    nombre = candidato.nombre_corto
    if not tema:
        return f"{nombre} {candidato.partido}".strip()
    if nombre.lower() in tema.lower():
        return tema
    return f"{nombre} {tema}"


def _invocar_tool(
    spec: ToolSpec,
    consulta: str,
    settings: Settings,
) -> ResultadoExtraccion:
    """Invoca una tool con manejo de errores defensivo.

    Las tools del Sprint 2 ya manejan sus propios HttpError y devuelven
    `ResultadoExtraccion`. Esta capa es por si una tool levanta una
    excepcion no esperada (bug, dependencia rota, etc.) — convierte
    cualquier excepcion no controlada a estado `error_red` para que el
    grafo no se caiga.
    """
    try:
        resultado = spec.ejecutar(consulta, settings=settings)
    except Exception as exc:  # noqa: BLE001 - es la red de seguridad final
        logger.exception("Tool %s lanzo excepcion no controlada", spec.nombre)
        return ResultadoExtraccion(
            fuente=f"tool:{spec.nombre}",
            tool=spec.nombre,
            consulta=consulta,
            estado="error_red",
            mensaje=(
                f"La tool {spec.nombre} lanzo una excepcion no controlada. "
                "Revisar logs."
            ),
            error=f"{exc.__class__.__name__}: {exc}",
        )

    if not isinstance(resultado, ResultadoExtraccion):
        # Una tool legacy (o Sprint 1 sin migrar) podria devolver un dict.
        # Lo intentamos coercer en lugar de fallar.
        if isinstance(resultado, dict):
            try:
                return ResultadoExtraccion.model_validate(resultado)
            except Exception:  # noqa: BLE001
                pass
        logger.warning(
            "Tool %s devolvio tipo inesperado %s; convertido a error_parseo",
            spec.nombre,
            type(resultado).__name__,
        )
        return ResultadoExtraccion(
            fuente=f"tool:{spec.nombre}",
            tool=spec.nombre,
            consulta=consulta,
            estado="error_parseo",
            mensaje=f"Tool devolvio tipo inesperado: {type(resultado).__name__}.",
        )

    return resultado


def extraer(
    pregunta: str,
    plan: PlanEjecucion,
    settings: Optional[Settings] = None,
) -> ContextoExtraido:
    """Ejecuta las tools del plan y agrega resultados.

    Args:
        pregunta: texto original del usuario; se reenvia a cada tool
            como `consulta`. (Sprint 2 no extrae nombres todavia: cada
            backend hace su propio full-text search sobre la pregunta.)
        plan: salida del planificador.
        settings: snapshot opcional; si es None se carga desde entorno.

    Returns:
        `ContextoExtraido` listo para el agente de contraste (Sprint 4).
    """
    cfg = settings if settings is not None else load_settings()

    # Plan vacio o intencion indefinida: no hay nada que extraer.
    if not plan or plan.intencion is Intencion.INDEFINIDA or not plan.tools:
        return ContextoExtraido(
            consulta=pregunta,
            tools_invocadas=[],
            tools_omitidas=list(plan.tools) if plan else [],
            resultados=[],
        )

    resultados: List[ResultadoExtraccion] = []
    invocadas: List[str] = []
    omitidas: List[str] = []

    # Filtrar tools delegadas a otros agentes (RAG -> Sprint 3).
    tools_aplicables = [t for t in plan.tools if t not in _TOOLS_DELEGADAS]
    omitidas.extend(t for t in plan.tools if t in _TOOLS_DELEGADAS)

    # Limite de seguridad sobre cuanto trabajo encadena el extractor.
    tools_a_ejecutar = tools_aplicables[: cfg.extraccion_max_tools]
    omitidas.extend(tools_aplicables[cfg.extraccion_max_tools:])

    for nombre in tools_a_ejecutar:
        try:
            spec = obtener(nombre)
        except KeyError:
            logger.warning("Plan referencia tool no registrada: %s", nombre)
            omitidas.append(nombre)
            resultados.append(
                ResultadoExtraccion(
                    fuente=f"tool:{nombre}",
                    tool=nombre,
                    consulta=pregunta,
                    estado="error_parseo",
                    mensaje=f"Tool {nombre!r} no esta registrada.",
                )
            )
            continue

        invocadas.append(nombre)
        consulta_efectiva = consulta_para_tool(pregunta, plan.candidato, nombre)
        resultado = _invocar_tool(spec, consulta_efectiva, cfg)
        resultados.append(resultado)

    return ContextoExtraido(
        consulta=pregunta,
        tools_invocadas=invocadas,
        tools_omitidas=omitidas,
        resultados=resultados,
    )


def nodo_extraccion(estado: EstadoGrafo) -> EstadoGrafo:
    """Envoltura del extractor como nodo LangGraph."""
    pregunta = estado.get("pregunta", "")
    plan = estado.get("plan")
    if plan is None:
        # Defensivo: el grafo deberia haber pasado por el planificador
        # antes. Si no, devolvemos contexto vacio para no caer el grafo.
        logger.warning("nodo_extraccion: estado sin plan; contexto vacio.")
        return {"contexto_extraido": ContextoExtraido(consulta=pregunta)}

    contexto = extraer(pregunta, plan)
    logger.debug(
        "Extraccion: %d tools invocadas, estados=%s",
        len(contexto.tools_invocadas),
        contexto.todos_los_estados,
    )
    return {"contexto_extraido": contexto}
