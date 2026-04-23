"""Stub de consulta a CNE - Cuentas Claras (financiacion de campanas).

Sprint 1: no consulta la fuente real. Sprint 2 sustituira el cuerpo por
un cliente de scraping o ingesta CSV contra Cuentas Claras.
"""

from __future__ import annotations

from ate.schemas.state import Intencion
from ate.tools.registry import ToolSpec, registrar


def consultar_cne(consulta: str) -> dict:
    """Stub: simula la estructura de respuesta de Cuentas Claras.

    Args:
        consulta: nombre del candidato o de la campana.

    Returns:
        Dict con esquema estable. `estado` es siempre `"stub"` en Sprint 1.
    """
    return {
        "fuente": "CNE - Cuentas Claras",
        "estado": "stub",
        "consulta": consulta,
        "resultados": [],
        "mensaje": (
            "Stub Sprint 1: se conectara a Cuentas Claras (CSV / scraping) "
            "en Sprint 2 para consultar aportes y financiacion de campana."
        ),
    }


registrar(
    ToolSpec(
        nombre="consultar_cne",
        descripcion=(
            "Consulta aportes, donantes y financiacion registrada en "
            "Cuentas Claras del Consejo Nacional Electoral (CNE)."
        ),
        intenciones=(Intencion.FINANCIACION,),
        ejecutar=consultar_cne,
        sprint_real=2,
    )
)
