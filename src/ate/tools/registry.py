"""Registro central de tools disponibles para el planificador.

Cada tool se registra una sola vez al importar su modulo. El registro
mantiene, ademas del callable, metadatos que el planificador usa para
decidir que tools son aplicables a una intencion dada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

from ate.schemas.state import Intencion

ToolCallable = Callable[[str], dict]


@dataclass(frozen=True)
class ToolSpec:
    """Descriptor estable de una tool.

    Atributos:
        nombre: identificador unico, usado por el planificador.
        descripcion: breve descripcion funcional (en espanol).
        intenciones: intenciones para las que esta tool es candidata.
        ejecutar: callable con firma `(consulta: str) -> dict`.
        sprint_real: sprint en el que este stub sera reemplazado por
            una implementacion real.
    """

    nombre: str
    descripcion: str
    intenciones: Tuple[Intencion, ...]
    ejecutar: ToolCallable
    sprint_real: int


_REGISTRO: Dict[str, ToolSpec] = {}


def registrar(spec: ToolSpec) -> ToolSpec:
    """Registra una tool. Falla si ya existe una con el mismo nombre."""
    if spec.nombre in _REGISTRO:
        raise ValueError(f"Tool duplicada: {spec.nombre!r}")
    _REGISTRO[spec.nombre] = spec
    return spec


def obtener(nombre: str) -> ToolSpec:
    """Devuelve el spec registrado; `KeyError` si no existe."""
    if nombre not in _REGISTRO:
        raise KeyError(f"Tool no registrada: {nombre!r}")
    return _REGISTRO[nombre]


def listar() -> List[ToolSpec]:
    """Lista de todos los tools registrados (orden de registro)."""
    return list(_REGISTRO.values())


def tools_para(intencion: Intencion) -> List[str]:
    """Nombres de tools candidatas para una intencion dada."""
    return [spec.nombre for spec in _REGISTRO.values() if intencion in spec.intenciones]
