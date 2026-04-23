"""Stub de busqueda de noticias y declaraciones recientes.

Sprint 1: no llama a ninguna API de busqueda. Sprints posteriores
reemplazaran el cuerpo por un cliente Tavily o Serper.
"""

from __future__ import annotations

from ate.schemas.state import Intencion
from ate.tools.registry import ToolSpec, registrar


def buscar_noticias(consulta: str) -> dict:
    """Stub: simula la estructura de respuesta del buscador de noticias.

    Args:
        consulta: termino de busqueda (nombre, tema, etc.).

    Returns:
        Dict con esquema estable. `estado` es siempre `"stub"` en Sprint 1.
    """
    return {
        "fuente": "Search API (Tavily / Serper)",
        "estado": "stub",
        "consulta": consulta,
        "resultados": [],
        "mensaje": (
            "Stub Sprint 1: la busqueda de noticias via Tavily o Serper "
            "se implementa en sprints posteriores."
        ),
    }


registrar(
    ToolSpec(
        nombre="buscar_noticias",
        descripcion=(
            "Busca noticias y declaraciones recientes sobre un candidato "
            "o tema mediante APIs de busqueda web."
        ),
        intenciones=(Intencion.NOTICIAS,),
        ejecutar=buscar_noticias,
        sprint_real=2,
    )
)
