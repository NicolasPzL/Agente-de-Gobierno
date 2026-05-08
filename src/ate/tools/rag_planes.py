"""Tool `buscar_plan_gobierno` - Sprint 3.

Sprint 1-2: stub que devolvia `no_configurado`.
Sprint 3: la tool delega al cliente RAG (`ate.rag.cliente`). El agente
RAG en su nodo dedicado del grafo es el consumidor principal; esta tool
existe para mantener el contrato del registro y permitir invocaciones
puntuales fuera del grafo (p.ej. desde scripts o tests).

Sigue siendo `sprint_real=3`. La firma `(consulta, *, settings, candidato=None)`
mantiene compatibilidad con el extractor (que la ignora — el RAG vive
en su propio nodo del grafo).
"""

from __future__ import annotations

from typing import Optional

from ate.candidatos.modelo import Candidato
from ate.config.settings import Settings, load_settings
from ate.schemas.state import Intencion, ResultadoExtraccion
from ate.tools.registry import ToolSpec, registrar

_NOMBRE = "buscar_plan_gobierno"
_FUENTE = "Planes de gobierno (RAG ChromaDB)"


def buscar_plan_gobierno(
    consulta: str,
    *,
    settings: Optional[Settings] = None,
    candidato: Optional[Candidato] = None,
) -> ResultadoExtraccion:
    """Busqueda semantica sobre los planes de gobierno indexados.

    Args:
        consulta: pregunta en lenguaje natural.
        settings: snapshot opcional.
        candidato: si se pasa, filtra a chunks de ese candidato.
    """
    cfg = settings if settings is not None else load_settings()
    consulta = consulta.strip()

    if not consulta:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="sin_datos",
            mensaje="Consulta vacia: no se invoco RAG.",
        )

    if cfg.ate_offline:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="offline",
            mensaje="ATE_OFFLINE=1: RAG no consultado.",
        )

    try:
        from ate.rag.cliente import abrir_cliente
    except ImportError:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="no_configurado",
            mensaje=(
                "ChromaDB no esta instalado. Ejecutar "
                "`pip install -e \".[dev]\"` para habilitar RAG."
            ),
        )

    try:
        cliente = abrir_cliente(cfg.rag_dir)
        total = cliente.contar()
    except Exception as exc:  # noqa: BLE001
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="error_red",
            mensaje=f"No se pudo abrir la base vectorial: {exc}",
        )

    if total == 0:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="no_configurado",
            mensaje=(
                "Base vectorial vacia. Ejecutar "
                "`python scripts/ingestar_planes.py` para indexar los PDFs "
                "de `public/Candidatos/` antes de consultar."
            ),
        )

    hits = cliente.buscar(
        consulta,
        k=cfg.rag_top_k,
        candidato_id=candidato.id if candidato else None,
    )

    if not hits:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="sin_datos",
            mensaje=(
                "RAG: sin pasajes relevantes"
                + (f" para {candidato.nombre_corto}" if candidato else "")
                + "."
            ),
        )

    resultados = [
        {
            "candidato_id": h.metadata.get("candidato_id"),
            "candidato": h.metadata.get("candidato_nombre"),
            "pdf": h.metadata.get("pdf"),
            "pagina": h.metadata.get("pagina"),
            "score": h.distancia,
            "chunk_id": h.chunk_id,
            "texto": h.texto,
        }
        for h in hits
    ]
    urls = sorted({r["pdf"] for r in resultados if r["pdf"]})

    return ResultadoExtraccion(
        fuente=_FUENTE,
        tool=_NOMBRE,
        consulta=consulta,
        estado="ok",
        resultados=resultados,
        total_resultados=len(resultados),
        urls_oficiales=urls,
        mensaje=(
            f"RAG devolvio {len(resultados)} pasaje(s)"
            + (f" del plan de {candidato.nombre_corto}" if candidato else " (multi-candidato)")
            + f" para '{consulta}'."
        ),
    )


registrar(
    ToolSpec(
        nombre=_NOMBRE,
        descripcion=(
            "Busqueda semantica sobre planes de gobierno oficiales "
            "ingeridos en ChromaDB (Sprint 3)."
        ),
        intenciones=(Intencion.PLAN_GOBIERNO,),
        ejecutar=buscar_plan_gobierno,
        sprint_real=3,
    )
)
