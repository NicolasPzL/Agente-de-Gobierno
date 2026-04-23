"""Stub de consulta a SECOP I y II.

Sprint 1: no consulta la API real. Sprint 2 sustituira el cuerpo por un
cliente Socrata / SQL contra `www.datos.gov.co` (datasets SECOP).
"""

from __future__ import annotations

from ate.schemas.state import Intencion
from ate.tools.registry import ToolSpec, registrar


def consultar_secop(consulta: str) -> dict:
    """Stub: simula la estructura de respuesta de SECOP.

    Args:
        consulta: nombre o cedula del candidato/contratista.

    Returns:
        Dict con esquema estable. `estado` es siempre `"stub"` en Sprint 1.
    """
    return {
        "fuente": "SECOP",
        "estado": "stub",
        "consulta": consulta,
        "resultados": [],
        "mensaje": (
            "Stub Sprint 1: se conectara a la API de SECOP I/II en Sprint 2 "
            "para consultar historial de contratacion publica."
        ),
    }


registrar(
    ToolSpec(
        nombre="consultar_secop",
        descripcion=(
            "Consulta el historial de contratacion publica del candidato "
            "en SECOP I y SECOP II."
        ),
        intenciones=(Intencion.CONTRATACION,),
        ejecutar=consultar_secop,
        sprint_real=2,
    )
)
