"""Tool real para CNE - Cuentas Claras (financiacion de campanas).

Tres modos de operacion (despachados por configuracion, en este orden de prioridad):

    1. **API publica del CNE 2026** (`ATE_CNE_USE_API=1`, default):
       cliente que usa los endpoints REST de la SPA Laravel del fondo
       CNG 2026 (`app_cng_2026.cne.gov.co`). No requiere credencial.
       Soporta:
           - lista de procesos electorales 2026
           - lista de organizaciones politicas
           - busqueda por nombre de organizacion (substring)
           - lookup de informe publico de un candidato si se conocen
             todos sus IDs (proceso/tipo/corporacion/.../candidato)

    2. **Dataset Socrata** (`ATE_CNE_DATASET=<id>`):
       cuando el CNE publique un dataset Socrata oficial, el cliente
       hace `$q=<consulta>` contra el.

    3. **CSV directo** (`ATE_CNE_CSV_URL=<url>`):
       descarga un CSV publicado por el CNE y filtra en memoria por
       coincidencia de subcadena.

Si los tres caminos fallan o devuelven sin_datos, la tool **declara
ausencia explicita** — nunca inventa donantes ni montos. Esa es la
unica garantia etica posible cuando una fuente publica no expone
busqueda libre.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Dict, List, Optional

import requests
from requests import RequestException

from ate.config.settings import Settings, load_settings
from ate.schemas.state import Intencion, ResultadoExtraccion
from ate.tools._cne_api import (
    BASE_API,
    URL_APP_PUBLIC,
    URL_PORTAL,
    CneApiClient,
    CneApiError,
)
from ate.tools._http import HttpError, estado_desde_error
from ate.tools._socrata import consulta_socrata, url_dataset
from ate.tools.registry import ToolSpec, registrar

logger = logging.getLogger(__name__)

_NOMBRE = "consultar_cne"
_FUENTE = "CNE - Cuentas Claras 2026"


# ---------------------------------------------------------------------------
# Modo 1: API publica del CNE 2026
# ---------------------------------------------------------------------------


def _consultar_api_publica(consulta: str, cfg: Settings) -> ResultadoExtraccion:
    """Consulta los endpoints publicos REST del CNE 2026.

    Estrategia (porque la SPA no expone busqueda libre por nombre):
        1. Lista procesos electorales (deberian ser los del 2026).
        2. Lista organizaciones politicas registradas.
        3. Hace match `consulta in nombre_organizacion` (case-insensitive,
           sin tildes).
        4. Si hay matches: los devuelve como resultados con estado=ok.
        5. Si NO hay matches: devuelve sin_datos pero incluye en
           `resultados` la lista de procesos 2026 disponibles, para que
           el agente pueda informar al usuario que existe el contexto
           pero el candidato/organizacion buscado no esta registrado.
    """
    if cfg.ate_offline:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="offline",
            urls_oficiales=[URL_APP_PUBLIC, URL_PORTAL],
            mensaje="ATE_OFFLINE=1: API CNE 2026 no consultada.",
        )

    client = CneApiClient(settings=cfg)

    # 1) Procesos electorales (catalogo).
    try:
        procesos = client.listar_procesos_electorales()
    except CneApiError as exc:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="error_red",
            urls_oficiales=[URL_APP_PUBLIC, URL_PORTAL],
            mensaje="No se pudo contactar la API publica del CNE 2026.",
            error=str(exc),
        )

    # 2) Organizaciones politicas (catalogo).
    try:
        organizaciones = client.listar_organizaciones_politicas()
    except CneApiError as exc:
        # No es fatal: ya tenemos procesos. Anotamos el error y seguimos.
        logger.warning("CNE: fallo listar organizaciones: %s", exc)
        organizaciones = []

    # 3) Match por nombre.
    q_norm = consulta.lower().strip()
    matches: List[Dict[str, Any]] = []
    if q_norm:
        for org in organizaciones:
            nombre = str(org.get("nombre", "")).lower()
            if q_norm in nombre or any(
                tok in nombre for tok in q_norm.split() if len(tok) > 3
            ):
                matches.append({
                    "tipo": "organizacion_politica",
                    "id": org.get("id"),
                    "nombre": org.get("nombre"),
                    "url_consulta": (
                        f"{URL_APP_PUBLIC}#/?org={org.get('id')}"
                    ),
                })

    procesos_2026 = [
        {
            "tipo": "proceso_electoral",
            "id": p.get("id"),
            "nombre": p.get("nombre"),
            "fecha": p.get("fecha"),
            "resolucion": p.get("resolucion"),
        }
        for p in procesos
        if "2026" in str(p.get("nombre", "")) or "2026" in str(p.get("fecha", ""))
    ]

    urls = [URL_APP_PUBLIC, URL_PORTAL]

    if matches:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="ok",
            resultados=matches + procesos_2026,
            total_resultados=len(matches),
            urls_oficiales=urls,
            mensaje=(
                f"CNE 2026: {len(matches)} organizacion(es) politica(s) coinciden "
                f"con '{consulta}'. Para detalle financiero por candidato, el "
                "portal exige navegar la jerarquia (proceso -> tipo -> "
                "corporacion -> circunscripcion -> departamento -> municipio "
                "-> organizacion -> candidato) — los IDs estan en `resultados`."
            ),
        )

    # Sin matches. Devolvemos los procesos 2026 como contexto disponible.
    if procesos_2026:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="sin_datos",
            resultados=procesos_2026,
            total_resultados=0,
            urls_oficiales=urls,
            mensaje=(
                f"CNE 2026: ningun candidato u organizacion publica coincide "
                f"con '{consulta}'. El portal no expone busqueda por nombre; "
                f"hay {len(procesos_2026)} proceso(s) electoral(es) 2026 "
                "disponibles en `resultados` para navegacion manual."
            ),
        )

    return ResultadoExtraccion(
        fuente=_FUENTE,
        tool=_NOMBRE,
        consulta=consulta,
        estado="sin_datos",
        urls_oficiales=urls,
        mensaje=(
            "CNE 2026 contactado pero no devolvio procesos ni organizaciones "
            "que coincidan con la consulta. Es posible que los datos del "
            "candidato aun no esten registrados (la fecha de cierre de "
            "campana es 2026-05-31)."
        ),
    )


# ---------------------------------------------------------------------------
# Modo 2: Dataset Socrata configurable
# ---------------------------------------------------------------------------


def _consultar_socrata(consulta: str, cfg: Settings) -> ResultadoExtraccion:
    try:
        filas, url_oficial = consulta_socrata(
            settings=cfg, dataset_id=cfg.cne_dataset, q=consulta
        )
    except HttpError as exc:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado=estado_desde_error(exc),
            urls_oficiales=[
                url_dataset(cfg.socrata_domain, cfg.cne_dataset),
                URL_PORTAL,
            ],
            mensaje=f"No se pudo consultar Cuentas Claras (Socrata): {exc.clase}.",
            error=str(exc),
        )

    if not filas:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="sin_datos",
            urls_oficiales=[url_oficial, URL_PORTAL],
            mensaje="Cuentas Claras (Socrata) no devolvio coincidencias.",
        )

    return ResultadoExtraccion(
        fuente=_FUENTE,
        tool=_NOMBRE,
        consulta=consulta,
        estado="ok",
        resultados=filas,
        total_resultados=len(filas),
        urls_oficiales=[url_oficial, URL_PORTAL],
        mensaje=f"Cuentas Claras devolvio {len(filas)} registros para '{consulta}'.",
    )


# ---------------------------------------------------------------------------
# Modo 3: CSV directo
# ---------------------------------------------------------------------------


def _filtrar_csv(filas: List[Dict[str, Any]], consulta: str) -> List[Dict[str, Any]]:
    if not consulta:
        return filas
    q = consulta.lower()
    return [
        fila for fila in filas
        if any(q in str(v).lower() for v in fila.values() if v is not None)
    ]


def _consultar_csv(consulta: str, cfg: Settings) -> ResultadoExtraccion:
    if cfg.ate_offline:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="offline",
            urls_oficiales=[cfg.cne_csv_url, URL_PORTAL],
            mensaje="ATE_OFFLINE=1: no se descargo el CSV de Cuentas Claras.",
        )

    try:
        resp = requests.get(
            cfg.cne_csv_url,
            timeout=cfg.http_timeout,
            headers={"User-Agent": "ATE/0.2 Cuentas Claras client"},
        )
    except RequestException as exc:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="error_red",
            urls_oficiales=[cfg.cne_csv_url, URL_PORTAL],
            mensaje="No se pudo descargar el CSV de Cuentas Claras.",
            error=str(exc),
        )
    if resp.status_code >= 400:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="error_http",
            urls_oficiales=[cfg.cne_csv_url, URL_PORTAL],
            mensaje=f"CSV de Cuentas Claras devolvio HTTP {resp.status_code}.",
            error=resp.text[:300],
        )

    try:
        reader = csv.DictReader(io.StringIO(resp.text))
        filas = list(reader)
    except csv.Error as exc:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="error_parseo",
            urls_oficiales=[cfg.cne_csv_url, URL_PORTAL],
            mensaje="No se pudo parsear el CSV de Cuentas Claras.",
            error=str(exc),
        )

    filtradas = _filtrar_csv(filas, consulta)
    if not filtradas:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="sin_datos",
            urls_oficiales=[cfg.cne_csv_url, URL_PORTAL],
            mensaje=(
                f"El CSV se descargo ({len(filas)} filas) pero ninguna "
                f"coincide con '{consulta}'."
            ),
            total_resultados=0,
        )

    truncado = filtradas[: cfg.http_max_resultados]
    return ResultadoExtraccion(
        fuente=_FUENTE,
        tool=_NOMBRE,
        consulta=consulta,
        estado="ok",
        resultados=truncado,
        total_resultados=len(filtradas),
        urls_oficiales=[cfg.cne_csv_url, URL_PORTAL],
        mensaje=(
            f"Cuentas Claras (CSV) devolvio {len(filtradas)} coincidencias "
            f"para '{consulta}'. Mostrando las primeras {len(truncado)}."
        ),
    )


# ---------------------------------------------------------------------------
# Entrypoint publico
# ---------------------------------------------------------------------------


def consultar_cne(
    consulta: str,
    *,
    settings: Optional[Settings] = None,
) -> ResultadoExtraccion:
    """Consulta CNE Cuentas Claras 2026.

    Orden de prioridad:
        1. Dataset Socrata (`ATE_CNE_DATASET`) — si se configura.
        2. CSV directo (`ATE_CNE_CSV_URL`) — si se configura.
        3. API publica del CNE 2026 (default si `ATE_CNE_USE_API=1`).

    Args:
        consulta: texto libre — nombre de candidato/organizacion o
            cedula. La API publica solo soporta busqueda por nombre de
            organizacion (la SPA del CNE no expone busqueda por nombre
            de candidato; eso requiere navegar la jerarquia con IDs).
        settings: snapshot opcional; si es None, se carga desde entorno.
    """
    cfg = settings if settings is not None else load_settings()
    consulta = consulta.strip()

    if not consulta:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="sin_datos",
            urls_oficiales=[URL_PORTAL, URL_APP_PUBLIC],
            mensaje="Consulta vacia: no se invoco Cuentas Claras.",
        )

    # Prioridad: Socrata explicito > CSV explicito > API publica > no_configurado
    if cfg.cne_dataset:
        return _consultar_socrata(consulta, cfg)
    if cfg.cne_csv_url:
        return _consultar_csv(consulta, cfg)
    if cfg.cne_use_api:
        return _consultar_api_publica(consulta, cfg)

    return ResultadoExtraccion(
        fuente=_FUENTE,
        tool=_NOMBRE,
        consulta=consulta,
        estado="no_configurado",
        urls_oficiales=[URL_PORTAL],
        mensaje=(
            "CNE Cuentas Claras: ningun backend habilitado. Por defecto "
            "ATE_CNE_USE_API=1 activa el cliente contra la API publica del "
            "fondo CNG 2026. Para usar otra fuente, configurar ATE_CNE_DATASET "
            f"o ATE_CNE_CSV_URL en .env. Portal oficial: {URL_PORTAL}"
        ),
    )


registrar(
    ToolSpec(
        nombre=_NOMBRE,
        descripcion=(
            "Consulta aportes, donantes y financiacion de campana en "
            "Cuentas Claras del CNE (API publica 2026, Socrata o CSV)."
        ),
        intenciones=(Intencion.FINANCIACION,),
        ejecutar=consultar_cne,
        sprint_real=2,
    )
)
