"""Agente validador - Sprint 4.

Responsabilidades:
    1. Recopilar todas las `urls_oficiales` citadas por las tools de
       extraccion (ContextoExtraido).
    2. Verificar que cada URL pertenezca a un dominio oficial colombiano
       reconocido (*.gov.co, datos.gov.co, procuraduria.gov.co, etc.).
    3. En modo online: verificar accesibilidad via HTTP HEAD.
    4. En modo offline: solo validacion de dominio (no se toca la red).
    5. Deduplicar URLs para no validar la misma fuente dos veces.
    6. Nunca inventar: si una URL no esta en la lista de dominios oficiales,
       se reporta como "no oficial" con el dominio detectado, sin especular
       sobre su contenido.

Dominios oficiales reconocidos (Colombia):
    - *.gov.co      (cualquier subdominio del TLD gubernamental colombiano)
    - datos.gov.co  (Portal de Datos Abiertos)
    - rnec.org.co   (Registraduria Nacional del Estado Civil)

Decisiones de diseno:
    - **Sin modificar extraccion**: el validador lee pero nunca escribe en
      `contexto_extraido`; es un consumidor puro.
    - **Deduplicacion**: varias tools pueden citar la misma URL base de
      datos.gov.co; se valida una sola vez.
    - **HTTP HEAD, no GET**: minimiza el trafico y evita descargar cuerpos.
    - **Tolerancia a errores de red**: si HEAD falla, `accesible=False` con
      la razon en `observacion`; no se propaga la excepcion al grafo.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from urllib.parse import urlparse

import requests

from ate.config.settings import Settings, load_settings
from ate.schemas.state import (
    ContextoExtraido,
    ContextoRag,
    ContextoValidacion,
    EstadoGrafo,
    ValidacionFuente,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reglas de dominio oficial
# ---------------------------------------------------------------------------
# Ademas de esta lista exacta, cualquier hostname que termine en ".gov.co"
# se considera oficial (cubre todos los ministerios y entidades del estado).
_DOMINIOS_OFICIALES_EXACTOS = frozenset(
    {
        "datos.gov.co",
        "contratacion.gov.co",
        "secop.gov.co",
        "procuraduria.gov.co",
        "cne.gov.co",
        "cgr.gov.co",
        "funcionpublica.gov.co",
        "minjusticia.gov.co",
        "dafp.gov.co",
        "rnec.org.co",
        "registraduria.gov.co",
        "presidencia.gov.co",
        "senado.gov.co",
        "camara.gov.co",
        "dian.gov.co",
        "fiscalia.gov.co",
        "corteconstitucional.gov.co",
        "consejodeestado.gov.co",
        "cortesuprema.gov.co",
        "mineducacion.gov.co",
        "mintransporte.gov.co",
        "mindefensa.gov.co",
        "minagricultura.gov.co",
        "minambiente.gov.co",
        "mincomercio.gov.co",
        "mininterior.gov.co",
        "minvivienda.gov.co",
        "minsalud.gov.co",
        "mintic.gov.co",
        "minenergia.gov.co",
        "mincultura.gov.co",
        "sic.gov.co",
        "supersalud.gov.co",
    }
)


def _extraer_dominio(url: str) -> str:
    """Extrae el hostname raiz de una URL, sin prefijo 'www.'."""
    try:
        hostname = urlparse(url).hostname or ""
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname.lower()
    except Exception:
        return ""


def _es_dominio_oficial(dominio: str) -> bool:
    """True si el dominio pertenece al gobierno colombiano.

    Acepta:
        - Cualquier hostname que termine en '.gov.co' (TLD gubernamental).
        - Dominios exactos en `_DOMINIOS_OFICIALES_EXACTOS` (cubre
          entidades con TLD distinto como 'rnec.org.co').
    """
    if not dominio:
        return False
    if dominio.endswith(".gov.co") or dominio == "gov.co":
        return True
    return dominio in _DOMINIOS_OFICIALES_EXACTOS


def _validar_solo_dominio(url: str) -> ValidacionFuente:
    """Valida la URL unicamente por dominio, sin tocar la red."""
    dominio = _extraer_dominio(url)
    es_oficial = _es_dominio_oficial(dominio)
    if es_oficial:
        observacion = f"Dominio '{dominio}' reconocido como fuente oficial colombiana."
    else:
        observacion = (
            f"Dominio '{dominio}' no pertenece a la lista de fuentes "
            "oficiales colombianas reconocidas."
        )
    return ValidacionFuente(
        url=url,
        es_oficial=es_oficial,
        accesible=None,
        dominio_detectado=dominio,
        observacion=observacion,
    )


def _validar_con_red(url: str, timeout: float) -> ValidacionFuente:
    """Valida la URL por dominio Y verifica accesibilidad via HTTP HEAD."""
    base = _validar_solo_dominio(url)
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        accesible = resp.status_code < 400
        sufijo = (
            f" | HTTP {resp.status_code}: "
            f"{'accesible' if accesible else 'inaccesible'}."
        )
    except requests.exceptions.Timeout:
        accesible = False
        sufijo = " | Timeout al verificar accesibilidad."
    except requests.exceptions.ConnectionError as exc:
        accesible = False
        sufijo = f" | Error de conexion: {exc}"
    except Exception as exc:  # noqa: BLE001 - red de seguridad
        accesible = False
        sufijo = f" | Error inesperado: {exc}"

    return ValidacionFuente(
        url=url,
        es_oficial=base.es_oficial,
        accesible=accesible,
        dominio_detectado=base.dominio_detectado,
        observacion=base.observacion + sufijo,
    )


def _recopilar_urls(
    contexto_extraido: Optional[ContextoExtraido],
) -> List[str]:
    """Recopila y deduplica todas las urls_oficiales del contexto extraido.

    Los pasajes RAG apuntan a rutas de archivo local (PDF), no a URLs web,
    por lo que no se validan aqui.
    """
    urls: List[str] = []
    vistas: set = set()
    if contexto_extraido is None:
        return urls
    for resultado in contexto_extraido.resultados:
        for url in resultado.urls_oficiales:
            if url and url not in vistas:
                urls.append(url)
                vistas.add(url)
    return urls


def validar(
    contexto_extraido: Optional[ContextoExtraido],
    contexto_rag: Optional[ContextoRag],
    settings: Optional[Settings] = None,
) -> ContextoValidacion:
    """Punto de entrada puro y testeable del agente validador.

    Args:
        contexto_extraido: salida del agente de extraccion (Sprint 2).
        contexto_rag: salida del agente RAG (Sprint 3). Actualmente no se
            extraen URLs de RAG (los pasajes apuntan a archivos locales).
        settings: snapshot de configuracion. Si None, se carga del entorno.

    Returns:
        `ContextoValidacion` con la lista de fuentes validadas y conteos.
    """
    cfg = settings if settings is not None else load_settings()
    urls = _recopilar_urls(contexto_extraido)

    if not urls:
        return ContextoValidacion(
            estado="sin_fuentes",
            mensaje="No se encontraron URLs para validar en el contexto extraido.",
        )

    fuentes_validadas: List[ValidacionFuente] = []
    for url in urls:
        if cfg.ate_offline:
            fuente = _validar_solo_dominio(url)
        else:
            fuente = _validar_con_red(url, timeout=cfg.http_timeout)
        fuentes_validadas.append(fuente)

    n_total = len(fuentes_validadas)
    n_oficiales = sum(1 for f in fuentes_validadas if f.es_oficial)
    n_no_oficiales = n_total - n_oficiales
    n_inaccesibles = sum(1 for f in fuentes_validadas if f.accesible is False)

    if cfg.ate_offline:
        estado: str = "offline"
        sufijo_msg = " (modo offline: solo se valido el dominio, no la accesibilidad)"
    else:
        estado = "ok"
        sufijo_msg = ""

    mensaje = (
        f"Validacion de {n_total} fuente(s): "
        f"{n_oficiales} oficial(es), {n_no_oficiales} no oficial(es), "
        f"{n_inaccesibles} inaccesible(s){sufijo_msg}."
    )

    return ContextoValidacion(
        fuentes_validadas=fuentes_validadas,
        total_fuentes=n_total,
        fuentes_oficiales=n_oficiales,
        fuentes_no_oficiales=n_no_oficiales,
        fuentes_inaccesibles=n_inaccesibles,
        estado=estado,  # type: ignore[arg-type]
        mensaje=mensaje,
    )


def nodo_validador(estado: EstadoGrafo) -> EstadoGrafo:
    """Envoltura del agente validador como nodo LangGraph."""
    contexto_extraido = estado.get("contexto_extraido")
    contexto_rag = estado.get("contexto_rag")

    resultado = validar(contexto_extraido, contexto_rag)
    logger.debug(
        "Validador: total=%d, oficiales=%d, no_oficiales=%d, estado=%s",
        resultado.total_fuentes,
        resultado.fuentes_oficiales,
        resultado.fuentes_no_oficiales,
        resultado.estado,
    )
    return {"validacion": resultado}
