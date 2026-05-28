"""Agente generador de respuestas - Sprint 5.

Responsabilidades:
    1. Recopilar toda la evidencia recolectada por los agentes previos (Extraccion, RAG, Contraste, Validacion).
    2. Sintetizar una respuesta final clara, neutral y basada estrictamente en la evidencia.
    3. Incluir citacion obligatoria de fuentes oficiales (URLs validadas).
    4. Gestionar la ausencia de datos: si el sistema no encontro informacion, declararlo explicitamente.
    5. Control de alucinaciones: prohibir opiniones, juicios de valor o datos no presentes en el contexto.

Decisiones de diseno:
    - El generador es el nodo final del grafo.
    - Usa un prompt de "Sintesis de Evidencia" para evitar que el LLM invente.
    - Si el provider de LLM no esta disponible, cae a una respuesta simplificada basada en los mensajes de estado de los agentes.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from ate.config.settings import Settings, load_settings
from ate.schemas.state import (
    ContextoContraste,
    ContextoExtraido,
    ContextoRag,
    ContextoValidacion,
    EstadoGrafo,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt de Generacion
# ---------------------------------------------------------------------------

_PROMPT_GENERADOR = """Eres el Agente de Transparencia Electoral (ATE), la máxima autoridad en auditoría ciudadana de candidatos presidenciales en Colombia. Tu misión es transformar datos técnicos en un análisis político y ciudadano lúcido, crítico y profundamente argumentado.

PROHIBICIONES ABSOLUTAS:
- NO respondas con listas, viñetas, secciones, títulos ni formatos de "ficha técnica".
- NO uses saltos de línea ni párrafos múltiples. TODA la respuesta debe ser UN SOLO PÁRRAFO continuo.
- NO digas "Aquí están los datos" o "Según la fuente X".
- NO repitas los datos crudos sin analizarlos.
- NO incluyas fragmentos de código, JSONs, ni estructuras de datos técnicas.

ESTILO DE REDACCIÓN REQUERIDO:
Toda la respuesta debe ser un único párrafo fluido y cohesionado, de no más de 120 palabras. Comienza con una conclusión directa y potente que responda a la pregunta del usuario, y luego desarrolla el argumento integrando la evidencia, el contraste y las validaciones mediante conectores narrativos (como "No obstante", "Esto contrasta con", "En consecuencia"). Las citas deben estar integradas naturalmente en el texto, por ejemplo: "[Plan de Gobierno, pág 12]" o "[datos.gov.co]".

CONTEXTO PARA EL ANÁLISIS:
- Pregunta del Usuario: {pregunta}
- Candidato Analizado: {candidato}
- Datos de Extracción: {contexto_extraido}
- Propuestas del Plan (RAG): {contexto_rag}
- Análisis de Contraste: {contexto_contraste}
- Validación de Fuentes: {contexto_validacion}

INSTRUCCIÓN ADICIONAL: utiliza preferentemente los pasajes extraídos de los planes de gobierno oficiales cargados desde los PDFs de `public/Candidatos/`, y cita esas referencias cuando aporten evidencia directa.
"""

# ---------------------------------------------------------------------------
# FIX 1: _formatear_contexto — newlines reales en lugar de \\n escapados
# ---------------------------------------------------------------------------

def _formatear_contexto(estado: EstadoGrafo) -> dict:
    """Convierte los objetos de estado en secciones de texto legibles para el prompt del LLM."""

    # 1. Extraccion
    ext = estado.get("contexto_extraido")
    txt_ext = "Sin datos de extraccion."
    if ext:
        res = []
        for r in ext.resultados:
            if r.estado in ("ok", "offline"):
                res.append(
                    _acortar_texto(
                        f"Fuente {r.fuente} ({r.estado}): {r.resultados} | URLs: {r.urls_oficiales}",
                        max_chars=240,
                    )
                )
                if len(res) >= 2:
                    break
        if res:
            txt_ext = "\n".join(res)


    # 2. RAG
    rag = estado.get("contexto_rag")
    txt_rag = "Sin pasajes de planes de gobierno."
    if rag and rag.hubo_pasajes:
        res = []
        for p in rag.pasajes[:2]:
            res.append(
                _acortar_texto(
                    f"Pag {p.pagina} ({p.candidato_nombre}): {p.texto}",
                    max_chars=260,
                )
            )
        txt_rag = "\n".join(res)


    # 3. Contraste
    con = estado.get("contraste")
    txt_con = "Sin analisis de contraste."
    if con and con.estado == "ok":
        if con.hubo_inconsistencias:
            res = []
            for i in con.inconsistencias[:3]:
                res.append(
                    _acortar_texto(
                        f"{i.tipo}: {i.descripcion} | Evidencia: {i.evidencia_dato}",
                        max_chars=240,
                    )
                )
            txt_con = "\n".join(res)

        else:
            txt_con = "No se detectaron inconsistencias entre propuestas y datos reales."

    # 4. Validacion
    val = estado.get("validacion")
    txt_val = "Sin validacion de fuentes."
    if val and val.estado == "ok":
        txt_val = f"Fuentes validadas: {val.fuentes_oficiales} oficiales, {val.fuentes_no_oficiales} no oficiales."

    # FIX: retornamos un dict con cada sección separada para pasarlas al prompt individualmente
    return {
        "extraido": txt_ext,
        "rag": txt_rag,
        "contraste": txt_con,
        "validacion": txt_val,
    }


def _acortar_texto(texto: str, max_chars: int = 250) -> str:
    texto = " ".join(str(texto).split())
    if len(texto) <= max_chars:
        return texto
    return texto[: max_chars - 3].rstrip() + "..."


def generar(pregunta: str, estado: EstadoGrafo, settings: Optional[Settings] = None, meta: Optional[dict] = None) -> str:
    """Sintetiza la respuesta final basada en el estado del grafo.

    Cae a un modo simplificado si el LLM no esta disponible.
    """
    cfg = settings if settings is not None else load_settings()

    if meta is not None:
        meta.update(
            llm_available=cfg.llm_available,
            llm_provider=cfg.llm_provider,
            used_fallback=None,
            llm_error=None,
            llm_error_type=None,
            ollama_host=cfg.ollama_host if cfg.llm_provider == "ollama" else None,
            ollama_model=cfg.ollama_model if cfg.llm_provider == "ollama" else None,
        )

    candidato = estado.get("plan").candidato.nombre_corto if estado.get("plan") and estado.get("plan").candidato else "Desconocido"
    secciones = _formatear_contexto(estado)

    if cfg.llm_available:
        try:
            if cfg.llm_provider == "anthropic":
                resultado = _invocar_llm_anthropic(pregunta, candidato, secciones, cfg)
            elif cfg.llm_provider == "ollama":
                resultado = _invocar_llm_ollama(pregunta, candidato, secciones, cfg)
            else:
                resultado = _generar_fallback(pregunta, candidato, estado)

            if meta is not None:
                meta["used_fallback"] = False
            return resultado
        except Exception as e:
            if meta is not None:
                meta["used_fallback"] = True
                meta["llm_error"] = str(e)
                meta["llm_error_type"] = e.__class__.__name__
            logger.warning("Error en LLM generador (%s); usando fallback.", e)

    if meta is not None:
        meta["used_fallback"] = True
        if meta.get("llm_error") is None:
            meta["llm_error"] = "LLM no disponible o no configurado"

    return _generar_fallback(pregunta, candidato, estado)


def _limpiar_resultado_crudo(resultado: any) -> str:
    """Convierte datos crudos (listas/dicts) en una frase compacta y legible."""
    if not resultado:
        return "no se encontraron datos relevantes"
    if isinstance(resultado, str):
        return resultado
    if isinstance(resultado, dict):
        claves = [k for k, v in resultado.items() if k not in ("id", "uuid", "id_dataset", "codigo") and v not in (None, "")]
        if claves:
            return f"información estructurada sobre {', '.join(claves[:3])}"
        return "información estructurada"
    if isinstance(resultado, list):
        if not resultado:
            return "no se encontraron datos relevantes"
        primera = resultado[0]
        if isinstance(primera, dict):
            claves = [k for k, v in primera.items() if k not in ("id", "uuid", "id_dataset", "codigo") and v not in (None, "")]
            if claves:
                return f"información relevante con campos {', '.join(claves[:3])}"
            return f"{len(resultado)} resultados estructurados"
        return f"{len(resultado)} resultados: {', '.join(str(item) for item in resultado[:3])}"
    return str(resultado)


def _generar_fallback(pregunta: str, candidato: str, estado: EstadoGrafo) -> str:
    """
    Crea una respuesta en un solo párrafo cuando el LLM no está disponible.
    Sustituye el formato de reporte por una narrativa continua y simple.
    """

    con = estado.get("contraste")
    ext = estado.get("contexto_extraido")
    rag = estado.get("contexto_rag")

    if con and con.estado == "ok" and con.hubo_inconsistencias:
        conclusion = (
            f"Análisis de Transparencia Electoral para {candidato}: el contraste detecta inconsistencias relevantes "
            f"entre las promesas del plan y los datos reales"
        )
    elif con and con.estado == "ok":
        conclusion = (
            f"Análisis de Transparencia Electoral para {candidato}: el contraste indica que las propuestas del plan guardan coherencia "
            f"con la evidencia disponible"
        )
    else:
        conclusion = (
            f"Análisis de Transparencia Electoral para {candidato}: no hay suficiente evidencia oficial para completar un contraste formal"
        )

    evidencias = []
    if ext:
        found_ext = [r for r in ext.resultados if r.estado in ("ok", "offline")]
        for r in found_ext[:2]:
            detalle = r.mensaje.strip() if r.mensaje else _limpiar_resultado_crudo(r.resultados)
            evidencias.append(f"según {r.fuente}, {detalle}")
    if evidencias:
        conclusion += ". Además, " + " y ".join(evidencias)

    plan_textos = []
    if rag and rag.hubo_pasajes:
        for p in rag.pasajes[:2]:
            texto = p.texto.strip().replace("\n", " ")
            frase = texto.split(".")[0]
            frase = frase[:150].rstrip()
            plan_textos.append(f"el plan oficial menciona que {frase} [Plan de Gobierno, pág {p.pagina}]")
    if plan_textos:
        conclusion += ". También, " + " y ".join(plan_textos)

    if con and con.estado == "ok" and con.hubo_inconsistencias:
        inconsistencias = [i.descripcion for i in con.inconsistencias[:2]]
        if inconsistencias:
            conclusion += ". En particular, " + " y ".join(inconsistencias)

    conclusion = conclusion.strip()
    if not conclusion.endswith("."):
        conclusion += "."

    if (not evidencias and not plan_textos) and (not con or con.estado != "ok"):
        return (
            f"Análisis de Transparencia Electoral para {candidato}: no se ha encontrado evidencia oficial suficiente "
            f"para generar un análisis detallado sobre {candidato} respecto a '{pregunta}'."
        )

    return conclusion


def _sanitizar_texto(texto: str) -> str:
    texto = str(texto or "").strip()
    texto = texto.replace('\\"', '"').replace("\\'", "'")
    texto = texto.replace("\\n", " ").replace("\\r", " ").replace("\\t", " ")
    texto = texto.replace("\\\\", "\\")
    texto = " ".join(texto.split())
    if texto.startswith("{") or texto.startswith("["):
        try:
            parsed = json.loads(texto)
            if isinstance(parsed, dict):
                items = []
                for key, value in parsed.items():
                    if len(items) >= 3:
                        break
                    items.append(f"{key}: {value}")
                if items:
                    return " ".join(items)
            if isinstance(parsed, list):
                return f"{len(parsed)} elementos en la respuesta"
        except json.JSONDecodeError:
            pass
    return texto


def _extraer_texto_ollama(body: dict) -> str:
    if not isinstance(body, dict):
        raise RuntimeError(f"Ollama devolvió respuesta inesperada: {body!r}")

    for key in ("response", "thinking"):
        if key in body and body[key]:
            return _sanitizar_texto(body[key])

    salida = []
    output = body.get("output")
    if isinstance(output, list):
        for item in output:
            if isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "output_text":
                            salida.append(str(part.get("text", "")))
                        elif isinstance(part, str):
                            salida.append(part)
                elif isinstance(content, str):
                    salida.append(content)
                elif isinstance(item.get("text"), str):
                    salida.append(item["text"])
                elif isinstance(item.get("message"), str):
                    salida.append(item["message"])
            elif isinstance(item, str):
                salida.append(item)

    if salida:
        return _sanitizar_texto(" ".join(salida))

    raise RuntimeError(f"Ollama no devolvió texto en 'response', 'thinking' ni 'output': {body!r}")


# ---------------------------------------------------------------------------
# FIX 2 + FIX 3: contexto real en el prompt y temperatura 0.4
# ---------------------------------------------------------------------------

def _invocar_llm_anthropic(pregunta: str, candidato: str, secciones: dict, settings: Settings) -> str:
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import SystemMessage, HumanMessage

    # FIX 3: temperatura 0.4 para respuestas más argumentadas y fluidas
    llm = ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0.4,
    )

    # FIX 2: se pasan las secciones reales al prompt en lugar de placeholders
    sistema = _PROMPT_GENERADOR.format(
        pregunta=pregunta,
        candidato=candidato,
        contexto_extraido=secciones["extraido"],
        contexto_rag=secciones["rag"],
        contexto_contraste=secciones["contraste"],
        contexto_validacion=secciones["validacion"],
    )

    usuario = "Por favor, genera la respuesta final siguiendo estrictamente las reglas de redacción analítica."

    messages = [
        SystemMessage(content=sistema),
        HumanMessage(content=usuario),
    ]

    resp = llm.invoke(messages)
    return resp.content


def _invocar_llm_ollama(pregunta: str, candidato: str, secciones: dict, settings: Settings) -> str:
    import json
    import urllib.request
    import urllib.error

    # FIX 2: se pasan las secciones reales al prompt en lugar de placeholders
    sistema = _PROMPT_GENERADOR.format(
        pregunta=pregunta,
        candidato=candidato,
        contexto_extraido=secciones["extraido"],
        contexto_rag=secciones["rag"],
        contexto_contraste=secciones["contraste"],
        contexto_validacion=secciones["validacion"],
    )

    usuario = "Por favor, genera la respuesta final siguiendo estrictamente las reglas de redacción analítica."
    prompt = f"{sistema}\n\n{usuario}"

    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.4, "max_output_tokens": 128},
    }

    url = f"{settings.ollama_host}/api/generate"
    timeout = settings.ollama_timeout

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return _extraer_texto_ollama(body)
        detalle = ""
        try:
            detalle = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass

        diagnostics = detalle.lower()
        if e.code == 404 or "model not found" in diagnostics or "unknown model" in diagnostics or "no model named" in diagnostics:
            logger.warning(f"Modelo {settings.ollama_model} no encontrado. Intentando descarga automática...")
            try:
                pull_payload = {"name": settings.ollama_model}
                pull_url = f"{settings.ollama_host}/api/pull"
                pull_req = urllib.request.Request(
                    pull_url,
                    data=json.dumps(pull_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(pull_req, timeout=10)
                logger.info("Descarga del modelo iniciada en segundo plano. La próxima consulta debería funcionar.")
            except Exception as pull_err:
                logger.error(f"Error al intentar descargar el modelo automáticamente: {pull_err}")

            raise RuntimeError(
                f"El modelo {settings.ollama_model} no está instalado o no se encuentra disponible. Intenté descargarlo automáticamente. Por favor, espera y vuelve a intentar."
            )

        raise RuntimeError(
            f"Ollama HTTP {e.code} en {url}: {detalle or e.reason}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama inalcanzable en {url}: {e.reason}") from e
    except TimeoutError as e:
        raise RuntimeError(f"Ollama excedió el timeout de {timeout}s en {url}") from e


def nodo_generador(estado: EstadoGrafo) -> EstadoGrafo:
    """Envoltura del generador como nodo LangGraph."""
    pregunta = estado.get("pregunta", "")
    meta: dict = {}
    resultado = generar(pregunta, estado, meta=meta)
    return {"respuesta_final": resultado, "llm_info": meta}