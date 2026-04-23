"""Stub de busqueda semantica sobre planes de gobierno (RAG).

Sprint 1: no hay base vectorial. Sprint 3 reemplazara el cuerpo por una
consulta contra ChromaDB/Pinecone con embeddings de los PDFs ingeridos.
"""

from __future__ import annotations

from ate.schemas.state import Intencion
from ate.tools.registry import ToolSpec, registrar


def buscar_plan_gobierno(consulta: str) -> dict:
    """Stub: simula la estructura de respuesta del agente RAG.

    Args:
        consulta: tema o pregunta sobre el plan de gobierno.

    Returns:
        Dict con esquema estable. `estado` es siempre `"stub"` en Sprint 1.
    """
    return {
        "fuente": "Planes de gobierno (RAG)",
        "estado": "stub",
        "consulta": consulta,
        "resultados": [],
        "mensaje": (
            "Stub Sprint 1: la ingesta de PDFs y la base vectorial se "
            "implementan en Sprint 3 (ChromaDB o Pinecone)."
        ),
    }


registrar(
    ToolSpec(
        nombre="buscar_plan_gobierno",
        descripcion=(
            "Busqueda semantica sobre planes de gobierno oficiales, para "
            "extraer propuestas relevantes a un tema."
        ),
        intenciones=(Intencion.PLAN_GOBIERNO,),
        ejecutar=buscar_plan_gobierno,
        sprint_real=3,
    )
)
