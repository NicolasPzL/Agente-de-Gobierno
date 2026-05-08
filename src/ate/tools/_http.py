"""Cliente HTTP compartido por las tools del Sprint 2.

Centraliza:
    - timeouts por defecto desde Settings,
    - manejo de errores de red / HTTP / JSON con clasificacion estable,
    - inyeccion del header Socrata `X-App-Token` cuando aplica,
    - punto unico de monkeypatch para tests.

Las tools nunca importan `requests` directamente; usan `http_get_json` /
`http_post_json` de este modulo. Asi los tests reemplazan una sola
funcion para cubrir todas las tools.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Mapping, Optional

import requests
from requests import RequestException

from ate.config.settings import Settings

logger = logging.getLogger(__name__)


class HttpError(Exception):
    """Error estructurado producido por el cliente HTTP.

    Atributos:
        clase: una de `red`, `http`, `parseo`, `offline`.
        detalle: mensaje legible (truncado si la fuente devuelve mucho texto).
        status: codigo HTTP cuando aplique.
        url: URL donde ocurrio el error (sin query, para no filtrar tokens).
    """

    def __init__(
        self,
        *,
        clase: str,
        detalle: str,
        status: Optional[int] = None,
        url: Optional[str] = None,
    ) -> None:
        self.clase = clase
        self.detalle = detalle
        self.status = status
        self.url = url
        super().__init__(self._render())

    def _render(self) -> str:
        partes = [self.clase, self.detalle]
        if self.status is not None:
            partes.append(f"http={self.status}")
        if self.url:
            partes.append(self.url)
        return " | ".join(partes)


def _user_agent() -> str:
    return "ATE/0.2 (https://github.com/MateoGiraldoT/agenteGobierno; contacto: mateogiraldost@gmail.com)"


def _headers_socrata(settings: Settings, extra: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """Construye los headers para llamadas Socrata (datos.gov.co / SECOP)."""
    headers: Dict[str, str] = {
        "User-Agent": _user_agent(),
        "Accept": "application/json",
    }
    if settings.socrata_app_token:
        headers["X-App-Token"] = settings.socrata_app_token
    if extra:
        headers.update(extra)
    return headers


def _ensure_online(settings: Settings, url: str) -> None:
    if settings.ate_offline:
        raise HttpError(clase="offline", detalle="ATE_OFFLINE=1: red deshabilitada", url=url)


def http_get_json(
    url: str,
    *,
    settings: Settings,
    params: Optional[Mapping[str, Any]] = None,
    headers: Optional[Mapping[str, str]] = None,
    timeout: Optional[float] = None,
    socrata: bool = False,
) -> Any:
    """GET HTTP que devuelve JSON parseado.

    Lanza `HttpError` con `clase` en {`red`, `http`, `parseo`, `offline`}
    para que la tool consumidora pueda mapear a `EstadoResultado`.
    """
    _ensure_online(settings, url)
    h = _headers_socrata(settings, headers) if socrata else {
        "User-Agent": _user_agent(),
        "Accept": "application/json",
        **(dict(headers) if headers else {}),
    }
    t = timeout if timeout is not None else settings.http_timeout
    try:
        resp = requests.get(url, params=params, headers=h, timeout=t)
    except requests.Timeout as exc:
        raise HttpError(clase="red", detalle=f"timeout despues de {t}s", url=url) from exc
    except RequestException as exc:
        raise HttpError(clase="red", detalle=str(exc), url=url) from exc

    if resp.status_code >= 400:
        raise HttpError(
            clase="http",
            detalle=resp.text[:500] if resp.text else resp.reason,
            status=resp.status_code,
            url=url,
        )
    try:
        return resp.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise HttpError(
            clase="parseo",
            detalle=f"respuesta no-JSON (primeros 200 chars): {resp.text[:200]!r}",
            url=url,
        ) from exc


def http_post_json(
    url: str,
    *,
    settings: Settings,
    json_body: Optional[Mapping[str, Any]] = None,
    headers: Optional[Mapping[str, str]] = None,
    timeout: Optional[float] = None,
) -> Any:
    """POST HTTP con cuerpo JSON que devuelve JSON parseado."""
    _ensure_online(settings, url)
    h: Dict[str, str] = {
        "User-Agent": _user_agent(),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if headers:
        h.update(headers)
    t = timeout if timeout is not None else settings.http_timeout
    try:
        resp = requests.post(url, json=json_body, headers=h, timeout=t)
    except requests.Timeout as exc:
        raise HttpError(clase="red", detalle=f"timeout despues de {t}s", url=url) from exc
    except RequestException as exc:
        raise HttpError(clase="red", detalle=str(exc), url=url) from exc

    if resp.status_code >= 400:
        raise HttpError(
            clase="http",
            detalle=resp.text[:500] if resp.text else resp.reason,
            status=resp.status_code,
            url=url,
        )
    try:
        return resp.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise HttpError(
            clase="parseo",
            detalle=f"respuesta no-JSON (primeros 200 chars): {resp.text[:200]!r}",
            url=url,
        ) from exc


def estado_desde_error(err: HttpError) -> str:
    """Mapea `HttpError.clase` al campo `estado` de `ResultadoExtraccion`."""
    return {
        "red": "error_red",
        "http": "error_http",
        "parseo": "error_parseo",
        "offline": "offline",
    }.get(err.clase, "error_red")
