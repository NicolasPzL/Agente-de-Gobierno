"""Stub de consulta al Portal de Datos Abiertos (datos.gov.co).

Sprint 1: no consulta la API real. Sprint 2 sustituira el cuerpo de
`consultar_datos_abiertos` por un cliente Socrata.
"""

from __future__ import annotations

from ate.schemas.state import Intencion
from ate.tools.registry import ToolSpec, registrar


def consultar_datos_abiertos(consulta: str) -> dict:
    """Stub: simula la estructura de respuesta de datos.gov.co.

    Args:
        consulta: nombre o identificador del candidato a consultar.

    Returns:
        Dict con esquema estable. `estado` es siempre `"stub"` en Sprint 1.
    """
    return {
        "fuente": "datos.gov.co",
        "estado": "stub",
        "consulta": consulta,
        "resultados": [],
        "mensaje": (
            "Stub Sprint 1: se conectara a la API Socrata de datos.gov.co "
            "en Sprint 2 para consultar sanciones, multas y procesos."
        ),
    }


registrar(
    ToolSpec(
        nombre="consultar_datos_abiertos",
        descripcion=(
            "Consulta sanciones, multas y procesos disciplinarios/fiscales/penales "
            "registrados en el Portal de Datos Abiertos."
        ),
        intenciones=(Intencion.DATOS_OFICIALES,),
        ejecutar=consultar_datos_abiertos,
        sprint_real=2,
    )
)
