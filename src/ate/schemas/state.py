"""Esquemas del estado del grafo y salidas de los agentes.

Sprint 1: `Intencion`, `PlanEjecucion`, `EstadoGrafo` minimo.
Sprint 2: agrega `ResultadoExtraccion` y `ContextoExtraido` para el
agente de extraccion.
Sprint 2.5: el plan ahora puede llevar un `Candidato` detectado para
afinar las consultas en cada tool.
Sprint 3: agrega `PasajeRag` y `ContextoRag` para el agente RAG.
Sprint 4: agrega `InconsistenciaPropuesta`, `ContextoContraste`,
`ValidacionFuente` y `ContextoValidacion` para los agentes de contraste
y validacion. Los campos se consumen por el generador (Sprint 5) sin
tocar la firma.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional, TypedDict, Union

from pydantic import BaseModel, Field

from ate.candidatos.modelo import Candidato


class Intencion(str, Enum):
    """Categorias de intencion que el planificador puede detectar."""

    DATOS_OFICIALES = "datos_oficiales"
    PLAN_GOBIERNO = "plan_gobierno"
    CONTRATACION = "contratacion"
    FINANCIACION = "financiacion"
    NOTICIAS = "noticias"
    INDEFINIDA = "indefinida"


class PlanEjecucion(BaseModel):
    """Salida estructurada del agente planificador."""

    intencion: Intencion
    tools: List[str] = Field(
        default_factory=list,
        description="Nombres de tools a invocar, en orden recomendado.",
    )
    razonamiento: str = Field(
        default="",
        description="Explicacion breve de por que se eligio esta intencion/tools.",
    )
    candidato: Optional[Candidato] = Field(
        default=None,
        description=(
            "Candidato detectado en la pregunta (Sprint 2.5). Si no es None, "
            "el extractor lo usa para reescribir la consulta por tool."
        ),
    )


# Estados terminales posibles de cada invocacion de tool. Esta enumeracion
# tipa el campo `estado` de `ResultadoExtraccion` y se hereda en sprint 4
# (validador) para decidir si una respuesta tiene evidencia citable.
EstadoResultado = Literal[
    "ok",                # consulta exitosa con resultados
    "sin_datos",         # consulta exitosa pero la fuente no tiene resultados
    "no_configurado",    # falta credencial o dataset; no se intento la consulta
    "error_red",         # timeout, DNS, conexion rechazada
    "error_http",        # 4xx / 5xx desde la fuente
    "error_parseo",      # respuesta llego pero no fue parseable
    "offline",           # ATE_OFFLINE=1 forzo no tocar la red
]


class ResultadoExtraccion(BaseModel):
    """Resultado normalizado de una invocacion de tool.

    Esta es la unidad de datos que viaja del agente de extraccion al de
    contraste/validador. Cualquier tool — Socrata, Tavily, scraping —
    debe normalizar su salida a este shape antes de incorporarse al
    estado del grafo. La estabilidad de este shape es la que permite
    que sprints siguientes consuman datos sin adapters.
    """

    fuente: str = Field(description="Etiqueta humana de la fuente, p.ej. 'SECOP II'.")
    tool: str = Field(description="Nombre de la tool registrada que produjo este resultado.")
    consulta: str = Field(description="Termino de busqueda enviado a la fuente.")
    estado: EstadoResultado = Field(description="Resultado terminal de la invocacion.")
    resultados: List[dict] = Field(
        default_factory=list,
        description="Filas / hits normalizados; vacio si estado != 'ok'.",
    )
    total_resultados: int = Field(
        default=0,
        description="Cantidad de resultados (puede no coincidir con len(resultados) si se trunco).",
    )
    urls_oficiales: List[str] = Field(
        default_factory=list,
        description="URLs oficiales asociadas (Sprint 4 las validara antes de citar).",
    )
    mensaje: str = Field(default="", description="Mensaje legible para humanos.")
    error: Optional[str] = Field(
        default=None,
        description="Detalle del error si estado en {error_red, error_http, error_parseo}.",
    )


class ContextoExtraido(BaseModel):
    """Conjunto de resultados producidos por el agente de extraccion."""

    resultados: List[ResultadoExtraccion] = Field(default_factory=list)
    consulta: str = Field(default="", description="Pregunta original del usuario.")
    tools_invocadas: List[str] = Field(default_factory=list)
    tools_omitidas: List[str] = Field(
        default_factory=list,
        description="Tools que estaban en el plan pero se saltaron (p.ej. plan_gobierno en Sprint 2).",
    )

    @property
    def hubo_alguna_consulta_exitosa(self) -> bool:
        return any(r.estado == "ok" for r in self.resultados)

    @property
    def todos_los_estados(self) -> List[str]:
        return [r.estado for r in self.resultados]


class PasajeRag(BaseModel):
    """Un fragmento recuperado de la base vectorial de planes de gobierno.

    Cada pasaje incluye el texto y la metadata necesaria para que el
    generador (Sprint 5) cite la fuente exacta.
    """

    texto: str = Field(description="Contenido del fragmento.")
    candidato_id: str = Field(description="Slug del candidato en CANDIDATOS_2026.")
    candidato_nombre: str = Field(description="Nombre legible para citar.")
    pdf: str = Field(description="Path relativo del PDF origen.")
    pagina: int = Field(default=0, description="Numero de pagina en el PDF (1-based).")
    chunk_id: str = Field(description="Identificador del chunk en ChromaDB.")
    score: float = Field(default=0.0, description="Distancia (mas bajo = mas cercano).")


class ContextoRag(BaseModel):
    """Salida del agente RAG (Sprint 3).

    El campo `candidato_filtro` indica si la busqueda se restringio a un
    candidato; si es None, se busco en toda la base.
    """

    consulta: str = ""
    candidato_filtro: Optional[str] = Field(
        default=None,
        description="Slug del candidato si se filtro la busqueda; None si fue global.",
    )
    pasajes: List[PasajeRag] = Field(default_factory=list)
    estado: Literal[
        "ok",
        "sin_datos",
        "no_configurado",   # base vectorial vacia o ChromaDB no instalado
        "offline",
        "error_red",        # cargando el modelo de embeddings
        "error_parseo",
    ] = "no_configurado"
    mensaje: str = ""

    @property
    def hubo_pasajes(self) -> bool:
        return self.estado == "ok" and bool(self.pasajes)


# ---------------------------------------------------------------------------
# Sprint 4: Contraste y Validacion
# ---------------------------------------------------------------------------

TipoInconsistencia = Literal[
    "propuesta_sin_contratos",   # el candidato propone pero SECOP no tiene contratos
    "contratos_sin_propuesta",   # hay contratos en SECOP pero no hay propuesta en el plan
    "sanciones_detectadas",      # la Procuraduria registra sanciones disciplinarias
    "inconsistencia_sectorial",  # propuesta en sector X pero contratos en otros sectores
]


class InconsistenciaPropuesta(BaseModel):
    """Una inconsistencia detectada entre propuesta y datos reales.

    Solo se crea con evidencia directa de los datos. Nunca se infiere ni
    se inventa. Si no hay datos suficientes, el ContextoContraste
    declara estado='sin_datos' en lugar de crear inconsistencias vacias.
    """

    tipo: TipoInconsistencia
    descripcion: str = Field(description="Descripcion legible de la inconsistencia.")
    evidencia_propuesta: str = Field(
        default="",
        description="Fragmento del plan de gobierno que genera la inconsistencia.",
    )
    evidencia_dato: str = Field(
        default="",
        description="Dato real (contrato, sancion) que contrasta con la propuesta.",
    )
    fuentes: List[str] = Field(
        default_factory=list,
        description="Nombres de las fuentes donde se encontro la evidencia.",
    )


class ContextoContraste(BaseModel):
    """Salida del agente de contraste (Sprint 4).

    Cruza la informacion de propuestas del plan de gobierno (ContextoRag)
    con los datos reales de las fuentes oficiales (ContextoExtraido).
    Nunca inventa: si no hay datos declara estado='sin_datos'.
    """

    candidato_id: Optional[str] = Field(
        default=None,
        description="Slug del candidato analizado; None si no se detecto candidato.",
    )
    inconsistencias: List[InconsistenciaPropuesta] = Field(default_factory=list)
    n_propuestas_analizadas: int = Field(
        default=0,
        description="Cantidad de pasajes RAG usados en el analisis.",
    )
    n_contratos_analizados: int = Field(
        default=0,
        description="Cantidad de contratos SECOP usados en el analisis.",
    )
    n_sanciones_analizadas: int = Field(
        default=0,
        description="Cantidad de registros de sanciones usados en el analisis.",
    )
    estado: Literal[
        "ok",            # contraste ejecutado (puede haber 0 inconsistencias)
        "sin_datos",     # no hay suficiente informacion para contrastar
        "sin_candidato", # no se detecto candidato; el contraste no aplica
        "error",
    ] = "sin_datos"
    mensaje: str = ""

    @property
    def hubo_inconsistencias(self) -> bool:
        return bool(self.inconsistencias)


class ValidacionFuente(BaseModel):
    """Resultado de validar una URL individual.

    En modo offline `accesible` es None porque no se hizo peticion HTTP.
    En modo online es True/False segun el codigo HTTP retornado.
    """

    url: str
    es_oficial: bool = Field(
        description=(
            "True si el dominio pertenece a la lista de fuentes oficiales "
            "colombianas reconocidas (*.gov.co, datos.gov.co, etc.)."
        ),
    )
    accesible: Optional[bool] = Field(
        default=None,
        description="True si HTTP HEAD retorno 2xx. None en modo offline.",
    )
    dominio_detectado: str = Field(
        default="",
        description="Dominio raiz extraido de la URL.",
    )
    observacion: str = Field(
        default="",
        description="Razon de aceptacion o rechazo de la fuente.",
    )


class ContextoValidacion(BaseModel):
    """Salida del agente validador (Sprint 4).

    Verifica que las URLs citadas por las tools de extraccion pertenezcan
    a dominios oficiales colombianos y, en modo online, que sean accesibles.
    """

    fuentes_validadas: List[ValidacionFuente] = Field(default_factory=list)
    total_fuentes: int = 0
    fuentes_oficiales: int = 0
    fuentes_no_oficiales: int = 0
    fuentes_inaccesibles: int = 0
    estado: Literal["ok", "sin_fuentes", "offline"] = "sin_fuentes"
    mensaje: str = ""

    @property
    def todas_oficiales(self) -> bool:
        return self.fuentes_no_oficiales == 0 and self.total_fuentes > 0


class EstadoGrafo(TypedDict, total=False):
    """Estado compartido del grafo LangGraph.

    Se llena progresivamente conforme se atraviesan los nodos. Cada nodo
    devuelve solo un dict parcial con los campos que aporta; LangGraph
    fusiona contra el estado vigente.
    """

    pregunta: str
    plan: Optional[PlanEjecucion]
    contexto_extraido: Optional[ContextoExtraido]   # Sprint 2
    contexto_rag: Optional[ContextoRag]             # Sprint 3
    contraste: Optional[ContextoContraste]          # Sprint 4
    validacion: Optional[ContextoValidacion]        # Sprint 4

    # --- Sprint 5: Salida final ---
    respuesta_final: Optional[str]
    llm_info: Optional[dict]

