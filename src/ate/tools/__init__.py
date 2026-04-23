"""Tools del sistema multiagente.

Sprint 1: todas las tools son stubs con firmas y esquemas de salida
estables. Sprints 2+ reemplazaran el cuerpo de cada tool por clientes
reales contra fuentes oficiales.

Importar cualquier modulo hijo registra su tool en `ate.tools.registry`.
Este `__init__` se encarga de disparar esos registros explicitamente.
"""

from ate.tools import (  # noqa: F401 - importados por efecto de registro
    busqueda_noticias,
    cne,
    datos_abiertos,
    rag_planes,
    secop,
)
from ate.tools.registry import ToolSpec, listar, obtener, tools_para

__all__ = ["ToolSpec", "listar", "obtener", "tools_para"]
