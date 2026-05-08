"""Helpers comunes a las tools que usan Socrata (datos.gov.co / SECOP).

Una sola funcion `consulta_socrata` ejecuta una busqueda full-text contra
un dataset Socrata, normaliza errores via `HttpError` y devuelve la lista
de filas (dicts JSON) y la URL canonica de la consulta para citacion.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ate.config.settings import Settings
from ate.tools._http import HttpError, http_get_json


def url_dataset(domain: str, dataset_id: str) -> str:
    """URL canonica del dataset (no del API) — util para citacion."""
    return f"https://{domain}/d/{dataset_id}"


def url_resource_json(domain: str, dataset_id: str) -> str:
    """URL del endpoint JSON del dataset."""
    return f"https://{domain}/resource/{dataset_id}.json"


def consulta_socrata(
    *,
    settings: Settings,
    dataset_id: str,
    q: str,
    limit: int | None = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Ejecuta una busqueda full-text Socrata.

    Args:
        settings: snapshot de configuracion ATE.
        dataset_id: identificador Socrata (p.ej. "jbjy-vk9h").
        q: termino de busqueda full-text (`$q`). Cadena vacia retorna
            las primeras N filas del dataset (raramente util pero
            soportado).
        limit: cantidad maxima de filas; default `settings.http_max_resultados`.

    Returns:
        Tupla `(filas, url_dataset)`. La URL del dataset es la que
        cita el agente generador en sprint 5.

    Raises:
        HttpError: para que la tool consumidora la mapee a `EstadoResultado`.
    """
    if not dataset_id:
        raise HttpError(
            clase="parseo",
            detalle="dataset_id vacio: el endpoint no esta configurado",
        )
    url = url_resource_json(settings.socrata_domain, dataset_id)
    params: Dict[str, Any] = {
        "$limit": limit if limit is not None else settings.http_max_resultados,
    }
    if q:
        params["$q"] = q
    data = http_get_json(url, settings=settings, params=params, socrata=True)
    if not isinstance(data, list):
        raise HttpError(
            clase="parseo",
            detalle=f"Socrata devolvio tipo {type(data).__name__}, esperaba list",
            url=url,
        )
    return data, url_dataset(settings.socrata_domain, dataset_id)
