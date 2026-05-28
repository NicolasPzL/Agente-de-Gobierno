"""Agente RAG - Sprint 3.

Responsabilidades:
    1. Decidir si la pregunta amerita busqueda en planes de gobierno.
       (Cualquier pregunta con `Intencion.PLAN_GOBIERNO` o que mencione
       un candidato detectado entra al RAG; el resto pasa de largo.)
    2. Construir la consulta semantica para el cliente RAG.
    3. Aplicar filtro por `candidato_id` cuando el plan lo proporciona.
    4. Empaquetar los pasajes recuperados en un `ContextoRag`.

Decisiones de diseno:
    - El agente RAG **no** invoca la tool `buscar_plan_gobierno` desde
      el registro: en su lugar, llama directamente al cliente. Esto
      permite que el agente decida los parametros (k, filtros) y que
      el flujo del grafo sea explicito (`__start__ -> planificador
      -> extraccion -> rag -> END`).
    - **Tolerancia a fallos**: si chromadb no esta instalado o la
      coleccion esta vacia, se devuelve `estado="no_configurado"` con
      un mensaje accionable. Nunca se inventa.
    - **Modo offline**: el RAG corre en disco — no toca red. Pero la
      primera carga de Chroma puede bajar el modelo de embeddings de
      HuggingFace; por eso el flag `ate_offline=True` salta la
      operacion para evitar esa descarga en CI.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from ate.config.settings import Settings, load_settings
from ate.schemas.state import (
    ContextoRag,
    EstadoGrafo,
    Intencion,
    PasajeRag,
    PlanEjecucion,
)

logger = logging.getLogger(__name__)


def _debe_invocar_rag(plan: Optional[PlanEjecucion]) -> bool:
    """True si el plan justifica activar la base vectorial.

    Reglas:
        - Plan ausente o intencion indefinida sin candidato: no.
        - Intencion plan_gobierno: si.
        - Cualquier intencion con candidato detectado: si — el RAG
          puede aportar contexto del plan del candidato incluso para
          preguntas sobre contratacion / sanciones / etc.
    """
    if plan is None:
        return False
    if plan.intencion is Intencion.PLAN_GOBIERNO:
        return True
    if plan.candidato is not None:
        return True
    return False


def _contexto_vacio(consulta: str, mensaje: str = "") -> ContextoRag:
    return ContextoRag(
        consulta=consulta,
        candidato_filtro=None,
        pasajes=[],
        estado="sin_datos",
        mensaje=mensaje or "RAG no se invoco para esta pregunta.",
    )


def consultar_rag(
    pregunta: str,
    plan: Optional[PlanEjecucion],
    settings: Optional[Settings] = None,
) -> ContextoRag:
    """Punto de entrada puro y testeable del agente RAG."""
    cfg = settings if settings is not None else load_settings()

    if not _debe_invocar_rag(plan):
        return _contexto_vacio(pregunta)

    if cfg.ate_offline:
        return ContextoRag(
            consulta=pregunta,
            candidato_filtro=plan.candidato.id if plan and plan.candidato else None,
            pasajes=[],
            estado="offline",
            mensaje="ATE_OFFLINE=1: RAG no consultado.",
        )

    # Importacion perezosa para que el resto del proyecto pueda correr
    # sin chromadb instalado (p.ej. CI minimo o demo de Sprint 1).
    try:
        from ate.rag.cliente import abrir_cliente
    except ImportError as exc:
        return ContextoRag(
            consulta=pregunta,
            candidato_filtro=plan.candidato.id if plan and plan.candidato else None,
            pasajes=[],
            estado="no_configurado",
            mensaje=(
                "ChromaDB no esta instalado. Ejecutar "
                "`pip install -e \".[dev]\"` para habilitar RAG."
            ),
        )

    try:
        cliente = abrir_cliente(cfg.rag_dir)
        # Si la coleccion esta vacia, no se intenta busqueda.
        if cliente.contar() == 0:
            return ContextoRag(
                consulta=pregunta,
                candidato_filtro=plan.candidato.id if plan and plan.candidato else None,
                pasajes=[],
                estado="no_configurado",
                mensaje=(
                    "Base vectorial vacia. Ejecutar "
                    "`python scripts/ingestar_planes.py` para indexar los "
                    "PDFs de `public/Candidatos/` antes de consultar."
                ),
            )
    except Exception as exc:  # noqa: BLE001 - chromadb puede fallar al abrir
        logger.exception("Fallo abrir cliente RAG")
        return ContextoRag(
            consulta=pregunta,
            candidato_filtro=plan.candidato.id if plan and plan.candidato else None,
            pasajes=[],
            estado="error_red",
            mensaje=f"No se pudo abrir la base vectorial: {exc}",
        )

    candidato_id = plan.candidato.id if plan and plan.candidato else None

    fallback_global = False
    try:
        hits = cliente.buscar(
            pregunta,
            k=cfg.rag_top_k,
            candidato_id=candidato_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Fallo busqueda RAG")
        return ContextoRag(
            consulta=pregunta,
            candidato_filtro=candidato_id,
            pasajes=[],
            estado="error_parseo",
            mensaje=f"Fallo de busqueda RAG: {exc}",
        )

    if not hits and candidato_id:
        try:
            global_hits = cliente.buscar(pregunta, k=cfg.rag_top_k)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Fallo busqueda RAG global de respaldo")
            return ContextoRag(
                consulta=pregunta,
                candidato_filtro=candidato_id,
                pasajes=[],
                estado="error_parseo",
                mensaje=f"Fallo de busqueda RAG global de respaldo: {exc}",
            )
        if global_hits:
            hits = global_hits
            candidato_id = None
            fallback_global = True

    if not hits:
        return ContextoRag(
            consulta=pregunta,
            candidato_filtro=candidato_id,
            pasajes=[],
            estado="sin_datos",
            mensaje=(
                "RAG: no se encontraron pasajes relevantes"
                + (f" para el candidato {candidato_id}" if candidato_id else "")
                + "."
            ),
        )

    pasajes: List[PasajeRag] = []
    for h in hits:
        meta = h.metadata or {}
        pasajes.append(
            PasajeRag(
                texto=h.texto,
                candidato_id=str(meta.get("candidato_id", "")),
                candidato_nombre=str(meta.get("candidato_nombre", "")),
                pdf=str(meta.get("pdf", "")),
                pagina=int(meta.get("pagina", 0) or 0),
                chunk_id=h.chunk_id,
                score=h.distancia,
            )
        )

    mensaje = (
        f"RAG: {len(pasajes)} pasaje(s)"
        + (f" del candidato {candidato_id}" if candidato_id else " (busqueda global)")
        + f" para '{pregunta}'."
    )
    if fallback_global:
        mensaje += " Se usaron resultados globales porque no se encontraron pasajes filtrados por candidato."

    return ContextoRag(
        consulta=pregunta,
        candidato_filtro=candidato_id,
        pasajes=pasajes,
        estado="ok",
        mensaje=mensaje,
    )


def nodo_rag(estado: EstadoGrafo) -> EstadoGrafo:
    """Envoltura del agente RAG como nodo LangGraph."""
    pregunta = estado.get("pregunta", "")
    plan = estado.get("plan")
    contexto = consultar_rag(pregunta, plan)
    logger.debug(
        "RAG: %d pasajes, estado=%s, filtro=%s",
        len(contexto.pasajes),
        contexto.estado,
        contexto.candidato_filtro,
    )
    return {"contexto_rag": contexto}
