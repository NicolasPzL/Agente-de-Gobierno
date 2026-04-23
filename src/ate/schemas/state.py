"""Esquemas del estado del grafo y salidas del agente planificador."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, TypedDict

from pydantic import BaseModel, Field


class Intencion(str, Enum):
    """Categorias de intencion que el planificador puede detectar.

    Cada categoria mapea a una o mas fuentes oficiales declaradas en el
    `README.md` del proyecto. `INDEFINIDA` se usa cuando la pregunta no
    encaja con certeza en ninguna otra categoria.
    """

    DATOS_OFICIALES = "datos_oficiales"
    PLAN_GOBIERNO = "plan_gobierno"
    CONTRATACION = "contratacion"
    FINANCIACION = "financiacion"
    NOTICIAS = "noticias"
    INDEFINIDA = "indefinida"


class PlanEjecucion(BaseModel):
    """Salida estructurada del agente planificador.

    En Sprint 1 esta es la unica estructura que fluye del planificador
    al nodo terminal. Sprints posteriores la consumiran para orquestar
    los demas agentes.
    """

    intencion: Intencion
    tools: List[str] = Field(
        default_factory=list,
        description="Nombres de tools a invocar, en orden recomendado.",
    )
    razonamiento: str = Field(
        default="",
        description="Explicacion breve de por que se eligio esta intencion/tools.",
    )


class EstadoGrafo(TypedDict, total=False):
    """Estado compartido del grafo LangGraph.

    Sprint 1 solo usa `pregunta` (input) y `plan` (output del planificador).
    Los campos comentados abajo son placeholders para sprints siguientes;
    se dejan en comentario a proposito para que la extension futura sea
    evidente sin ensuciar el estado actual.
    """

    pregunta: str
    plan: Optional[PlanEjecucion]

    # --- Hooks para sprints futuros (no poblar en Sprint 1) ---
    # contexto_extraido: dict      # Sprint 2: resultado del agente de extraccion
    # contexto_rag: dict           # Sprint 3: pasajes del plan de gobierno
    # contraste: dict              # Sprint 4: inconsistencias propuesta vs hechos
    # validacion: dict             # Sprint 4: verificacion de URLs y fuentes
    # respuesta_final: str         # Sprint 5: texto generado con citacion
