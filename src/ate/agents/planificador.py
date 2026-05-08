"""Agente planificador del Sprint 1.

Responsabilidades:
    1. Detectar la intencion de la pregunta del usuario.
    2. Elegir la lista ordenada de tools aplicables.
    3. Exponer ambos resultados en un `PlanEjecucion` observable/testeable.

Dos caminos de clasificacion:
    - Determinista por palabras clave (default). No requiere red ni API
      keys; es el camino usado en CI y pruebas locales.
    - LLM estructurado (opt-in). Se activa configurando
      `ATE_LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`. Usa
      `with_structured_output` de `langchain-anthropic` para garantizar
      que la salida sea un `PlanEjecucion` valido.
"""

from __future__ import annotations

import json
import logging
import unicodedata
import urllib.error
import urllib.request
from typing import Tuple

from ate.candidatos import detectar_candidato
from ate.config.settings import Settings, load_settings
from ate.schemas.state import EstadoGrafo, Intencion, PlanEjecucion
from ate.tools import tools_para

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Clasificacion determinista por palabras clave
# ----------------------------------------------------------------------
#
# Orden importa: la primera coincidencia gana. Por eso las categorias
# mas especificas (financiacion, contratacion) van antes que las mas
# genericas (plan de gobierno, noticias). Palabras normalizadas sin
# tildes para evitar ambigüedades de entrada.
_PALABRAS_CLAVE: tuple[tuple[Intencion, tuple[str, ...]], ...] = (
    (
        Intencion.FINANCIACION,
        (
            "financiacion",
            "financiamiento",
            "donante",
            "donantes",
            "aporte",
            "aportes",
            "cuentas claras",
            "ingresos de campana",
        ),
    ),
    (
        Intencion.CONTRATACION,
        (
            "secop",
            "contrato",
            "contratos",
            "contratacion",
            "licitacion",
            "licitaciones",
            "proveedor",
            "contratista",
            "adjudicacion",
        ),
    ),
    (
        Intencion.DATOS_OFICIALES,
        (
            "sancion",
            "sanciones",
            "multa",
            "multas",
            "inhabilidad",
            "antecedentes",
            "proceso disciplinario",
            "proceso fiscal",
            "proceso penal",
            "disciplinario",
        ),
    ),
    (
        Intencion.PLAN_GOBIERNO,
        (
            "plan de gobierno",
            "propone",
            "proponen",
            "propuesta",
            "propuestas",
            "programa de gobierno",
            "promete",
            "promesa",
            "eje programatico",
            "pilar",
            "plantea",
        ),
    ),
    (
        Intencion.NOTICIAS,
        (
            "noticia",
            "noticias",
            "declcion",
            "declaracioaranes",
            "dijo",
            "ultima hora",
            "reciente",
            "entrevista",
        ),
    ),
)


def _normalizar(texto: str) -> str:
    """Minusculas + strip + quita diacriticos (NFD)."""
    texto = texto.lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def clasificar_por_palabras(pregunta: str) -> Tuple[Intencion, str]:
    """Clasifica la intencion buscando palabras clave normalizadas.

    Es determinista y no toca la red — seguro de usar en CI y como
    fallback cuando el LLM no esta disponible.

    Returns:
        (intencion, razonamiento): razonamiento explica que palabra
        clave gatillo la decision, util para trazabilidad.
    """
    q = _normalizar(pregunta)
    for intencion, palabras in _PALABRAS_CLAVE:
        for palabra in palabras:
            if palabra in q:
                return intencion, f"Palabra clave detectada: '{palabra}'."
    return Intencion.INDEFINIDA, "Ninguna palabra clave reconocida."


# ----------------------------------------------------------------------
# Clasificacion vía LLM estructurado (opt-in)
# ----------------------------------------------------------------------

_PROMPT_LLM = """Clasifica la pregunta del usuario en UNA unica categoria de intencion \
para un sistema de auditoria electoral colombiano.

Categorias validas:
- datos_oficiales: sanciones, multas, inhabilidades, antecedentes disciplinarios/fiscales/penales.
- plan_gobierno: propuestas, promesas, programa o ejes de un candidato.
- contratacion: contratos publicos, SECOP, licitaciones, adjudicaciones.
- financiacion: aportes, donantes, Cuentas Claras, financiacion de campana.
- noticias: declaraciones recientes, notas de prensa, entrevistas.
- indefinida: si no encaja con certeza en ninguna de las anteriores.

Responde SOLO con el JSON del esquema. No emitas juicios de valor.

Pregunta: {pregunta}
"""


def clasificar_con_llm(pregunta: str, settings: Settings) -> Tuple[Intencion, str]:
    """Clasifica la intencion con un LLM estructurado.

    Despacha segun `settings.llm_provider`. Cae hacia el clasificador por
    palabras clave si el cliente LLM no esta disponible o falla,
    registrando un warning.
    """
    try:
        if settings.llm_provider == "anthropic":
            return _invocar_llm_anthropic(pregunta, settings)
        if settings.llm_provider == "ollama":
            return _invocar_llm_ollama(pregunta, settings)
        raise RuntimeError(
            f"provider {settings.llm_provider!r} aun no soporta clasificacion LLM"
        )
    except Exception as exc:
        logger.warning(
            "LLM no disponible (%s: %s); uso fallback determinista.",
            exc.__class__.__name__,
            exc,
        )
        intencion, razon = clasificar_por_palabras(pregunta)
        return intencion, f"{razon} (LLM no disponible: {exc.__class__.__name__})"


def _invocar_llm_anthropic(pregunta: str, settings: Settings) -> Tuple[Intencion, str]:
    """Invoca Claude via `langchain-anthropic` con salida estructurada."""
    if settings.llm_provider != "anthropic":
        raise RuntimeError(
            f"provider configurado ({settings.llm_provider!r}) no es 'anthropic'"
        )
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY no configurada")

    # Importacion perezosa: el paquete es opcional (extras `dev` o `llm-anthropic`).
    from langchain_anthropic import ChatAnthropic
    from pydantic import BaseModel, Field

    class _Clasificacion(BaseModel):
        intencion: Intencion = Field(description="Categoria detectada.")
        razonamiento: str = Field(description="Breve justificacion.")

    llm = ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0,
    )
    estructurado = llm.with_structured_output(_Clasificacion)
    resultado: _Clasificacion = estructurado.invoke(_PROMPT_LLM.format(pregunta=pregunta))
    return resultado.intencion, resultado.razonamiento or "(sin razonamiento del LLM)"


# Instruccion adicional que se concatena al prompt base para forzar JSON
# valido. El endpoint `/api/generate` de Ollama acepta `format: "json"`
# para garantizar salida JSON parseable (disponible desde Ollama 0.1.24,
# anterior al soporte de JSON Schema en `/api/chat`). Esto es lo mismo
# que usa el laboratorio 1 cuando se conecta a Ollama local.
_OLLAMA_JSON_SUFFIX = (
    "\n\nResponde UNICAMENTE con un JSON valido del siguiente esquema "
    '(sin markdown, sin texto antes o despues): '
    '{"intencion": "<una de: datos_oficiales, plan_gobierno, '
    'contratacion, financiacion, noticias, indefinida>", '
    '"razonamiento": "<una frase breve>"}'
)


def _invocar_llm_ollama(pregunta: str, settings: Settings) -> Tuple[Intencion, str]:
    """Invoca un modelo local Ollama via `/api/generate` con `format=json`.

    Mantiene el patron del laboratorio 1 del curso:
    - endpoint `/api/generate` (no `/api/chat`, que no existe en todas
      las versiones de Ollama),
    - `prompt` como string unico,
    - `format: "json"` para forzar JSON parseable,
    - campo `response` como salida del modelo.

    Usa `urllib` (stdlib) para no anadir dependencias.
    """
    if settings.llm_provider != "ollama":
        raise RuntimeError(
            f"provider configurado ({settings.llm_provider!r}) no es 'ollama'"
        )
    if not settings.ollama_model:
        raise RuntimeError("OLLAMA_MODEL no configurado")

    prompt = _PROMPT_LLM.format(pregunta=pregunta) + _OLLAMA_JSON_SUFFIX
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        # `think: False` desactiva el modo "thinking" en modelos que lo
        # traen activo por defecto (qwen3, deepseek-r1, etc.). Sin esto
        # el JSON sale en `thinking` y `response` queda vacio.
        "think": False,
        "options": {"temperature": 0},
    }
    url = f"{settings.ollama_host}/api/generate"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=settings.ollama_timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detalle = ""
        try:
            detalle = exc.read().decode("utf-8", errors="ignore")
        except Exception:  # pragma: no cover - defensivo
            pass
        raise RuntimeError(
            f"Ollama devolvio HTTP {exc.code} en {url} "
            f"(modelo={settings.ollama_model!r}): {detalle or exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama inalcanzable en {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(
            f"Ollama excedio el timeout de {settings.ollama_timeout}s en {url}"
        ) from exc

    # `response` es el campo estandar. Algunos modelos de razonamiento
    # (qwen3-vl, deepseek-r1) pueden dejarlo vacio y emitir el JSON en
    # `thinking` aunque enviemos `think: false`; usamos ese campo como
    # respaldo antes de rendirnos.
    contenido = body.get("response") or body.get("thinking") or ""
    if not contenido:
        raise RuntimeError(f"Respuesta de Ollama sin 'response' ni 'thinking': {body!r}")

    try:
        parsed = json.loads(contenido)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Ollama devolvio contenido no-JSON pese a format=json: {contenido!r}"
        ) from exc

    intencion_raw = parsed.get("intencion")
    razonamiento = parsed.get("razonamiento") or "(sin razonamiento del LLM)"
    try:
        intencion = Intencion(intencion_raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Intencion invalida del LLM: {intencion_raw!r}"
        ) from exc

    return intencion, razonamiento


# ----------------------------------------------------------------------
# Entrypoints publicos (funcion + nodo LangGraph)
# ----------------------------------------------------------------------


def planificar(pregunta: str, settings: Settings | None = None) -> PlanEjecucion:
    """Genera el plan de ejecucion para una pregunta.

    Sprint 2.5: ademas de clasificar la intencion, detecta el candidato
    mencionado (si lo hay) para que el extractor pueda reescribir la
    consulta por tool.

    Args:
        pregunta: texto del usuario.
        settings: configuracion a usar. Si es `None` se carga desde entorno.

    Returns:
        `PlanEjecucion` con intencion, tools, razonamiento y candidato.
    """
    if not pregunta or not pregunta.strip():
        return PlanEjecucion(
            intencion=Intencion.INDEFINIDA,
            tools=[],
            razonamiento="Pregunta vacia.",
        )

    cfg = settings if settings is not None else load_settings()

    if cfg.llm_available:
        intencion, razon = clasificar_con_llm(pregunta, cfg)
    else:
        intencion, razon = clasificar_por_palabras(pregunta)

    # Deteccion deterministica del candidato (no toca red).
    candidato = detectar_candidato(pregunta)
    if candidato is not None:
        razon = f"{razon} Candidato detectado: {candidato.nombre_corto} ({candidato.partido})."

    # Si la pregunta menciona un candidato pero la intencion quedo
    # `indefinida`, dejamos `indefinida` (el usuario quizas pregunto
    # algo que no encaja en las categorias). El validador del Sprint 4
    # decidira que hacer.

    return PlanEjecucion(
        intencion=intencion,
        tools=tools_para(intencion),
        razonamiento=razon.strip(),
        candidato=candidato,
    )


def nodo_planificador(estado: EstadoGrafo) -> EstadoGrafo:
    """Envoltura del planificador como nodo LangGraph.

    Lee `pregunta` del estado y devuelve una actualizacion parcial
    con `plan`. El resto del estado se preserva.
    """
    pregunta = estado.get("pregunta", "")
    plan = planificar(pregunta)
    logger.debug("Plan generado: %s", plan.model_dump())
    return {"plan": plan}
