"""Tests del cliente para la API publica del CNE 2026.

Mockean `requests.Session` (porque el cliente usa una sesion persistente
con cookies). No tocan red. Verifican:
    - listado de procesos / organizaciones,
    - manejo de CSRF (el cliente envia X-XSRF-TOKEN tras GET inicial),
    - busqueda por substring en organizaciones,
    - estado=ok cuando hay matches,
    - estado=sin_datos cuando no hay matches pero si procesos 2026,
    - estado=error_red cuando la API cae,
    - integracion via consultar_cne con settings.cne_use_api=True.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import replace
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from ate.config.settings import Settings, load_settings
from ate.tools._cne_api import CneApiClient, CneApiError
from ate.tools.cne import consultar_cne


def _cfg(**overrides: Any) -> Settings:
    base = load_settings()
    overrides.setdefault("ate_offline", False)
    overrides.setdefault("cne_use_api", True)
    return replace(base, **overrides)


# ---------- helpers para mockear requests.Session ----------


class _FakeResp:
    def __init__(self, *, status_code: int = 200, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or ""

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON")
        return self._payload


class _FakeCookies(dict):
    """Mimics requests.cookies.RequestsCookieJar minimo para .get."""
    def get(self, k, default=None):
        return super().get(k, default)


def _fake_session_factory(handlers: Dict[str, Any]):
    """Construye una sesion fake. `handlers` mapea metodo+path -> _FakeResp.

    Ej: {'GET /informes/cne': _FakeResp(...), 'GET /getProcesosElectoralesPublic': ...}
    """
    s = MagicMock()
    s.headers = {}
    s.cookies = _FakeCookies({"XSRF-TOKEN": urllib.parse.quote("token-fake-123")})
    s.verify = True

    def _resolver(method: str, url: str, **kwargs):
        # extraer el path despues de /fondo_cng_2026/public
        marker = "/fondo_cng_2026/public"
        idx = url.find(marker)
        path = url[idx + len(marker):] if idx >= 0 else url
        clave = f"{method.upper()} {path}"
        if clave in handlers:
            return handlers[clave]
        return _FakeResp(status_code=404, text=f"unmocked {clave}")

    s.get = MagicMock(side_effect=lambda url, **kw: _resolver("GET", url, **kw))
    s.post = MagicMock(side_effect=lambda url, **kw: _resolver("POST", url, **kw))
    s.put = MagicMock(side_effect=lambda url, **kw: _resolver("PUT", url, **kw))
    return s


# ---------- tests del client ----------


def test_cliente_setea_xsrf_tras_get_inicial(monkeypatch):
    handlers = {
        "GET /informes/cne": _FakeResp(payload=None, text="<html/>"),
        "GET /getProcesosElectoralesPublic": _FakeResp(payload=[
            {"id": 1, "nombre": "ELECCIONES CONGRESO - 2026", "fecha": "2026-03-08"}
        ]),
    }
    sesion = _fake_session_factory(handlers)
    monkeypatch.setattr("ate.tools._cne_api.requests.Session", lambda: sesion)

    client = CneApiClient(settings=_cfg())
    procesos = client.listar_procesos_electorales()

    # Verifica que el header XSRF se haya seteado tras el GET inicial.
    assert sesion.headers.get("X-XSRF-TOKEN") == "token-fake-123"
    assert procesos == [{"id": 1, "nombre": "ELECCIONES CONGRESO - 2026", "fecha": "2026-03-08"}]


def test_cliente_listar_organizaciones(monkeypatch):
    handlers = {
        "GET /informes/cne": _FakeResp(payload=None, text=""),
        "GET /consultar/selecOganizacionPoliticaPublic": _FakeResp(payload={
            "organizaciones": [
                {"id": 28, "nombre": "MOVIMIENTO POLITICO PACTO HISTORICO"},
                {"id": 7, "nombre": "AICO"},
            ]
        }),
    }
    sesion = _fake_session_factory(handlers)
    monkeypatch.setattr("ate.tools._cne_api.requests.Session", lambda: sesion)

    orgs = CneApiClient(settings=_cfg()).listar_organizaciones_politicas()
    assert {o["id"] for o in orgs} == {28, 7}


def test_cliente_lanza_apierror_si_get_falla(monkeypatch):
    import requests as _req
    handlers = {"GET /informes/cne": _FakeResp(payload=None)}
    sesion = _fake_session_factory(handlers)

    def fail_get(url, **kw):
        if "informes/cne" in url:
            return _FakeResp(payload=None)
        raise _req.exceptions.ConnectionError("dns down")
    sesion.get = MagicMock(side_effect=fail_get)
    monkeypatch.setattr("ate.tools._cne_api.requests.Session", lambda: sesion)

    with pytest.raises(CneApiError, match="GET .* fallo"):
        CneApiClient(settings=_cfg()).listar_procesos_electorales()


def test_cliente_lanza_apierror_en_http_500(monkeypatch):
    handlers = {
        "GET /informes/cne": _FakeResp(payload=None),
        "GET /getProcesosElectoralesPublic": _FakeResp(status_code=500, text="boom"),
    }
    sesion = _fake_session_factory(handlers)
    monkeypatch.setattr("ate.tools._cne_api.requests.Session", lambda: sesion)

    with pytest.raises(CneApiError, match="HTTP 500"):
        CneApiClient(settings=_cfg()).listar_procesos_electorales()


# ---------- tests de la tool consultar_cne en modo API ----------


def test_consultar_cne_api_match_organizacion(monkeypatch):
    handlers = {
        "GET /informes/cne": _FakeResp(payload=None),
        "GET /getProcesosElectoralesPublic": _FakeResp(payload=[
            {"id": 5, "nombre": "PRESIDENCIA 1A VUELTA - 2026", "fecha": "2026-05-31",
             "resolucion": "RES X DE 2026"}
        ]),
        "GET /consultar/selecOganizacionPoliticaPublic": _FakeResp(payload={
            "organizaciones": [
                {"id": 28, "nombre": "MOVIMIENTO POLITICO PACTO HISTORICO"},
                {"id": 9, "nombre": "PARTIDO LIBERAL"},
            ]
        }),
    }
    sesion = _fake_session_factory(handlers)
    monkeypatch.setattr("ate.tools._cne_api.requests.Session", lambda: sesion)

    r = consultar_cne("Pacto Historico", settings=_cfg())
    assert r.estado == "ok"
    assert r.total_resultados == 1
    # Se incluye la organizacion + los procesos 2026 como referencia
    tipos = [item["tipo"] for item in r.resultados]
    assert "organizacion_politica" in tipos
    assert "proceso_electoral" in tipos
    assert any("app_cng_2026" in u for u in r.urls_oficiales)


def test_consultar_cne_api_sin_match_devuelve_procesos_2026(monkeypatch):
    handlers = {
        "GET /informes/cne": _FakeResp(payload=None),
        "GET /getProcesosElectoralesPublic": _FakeResp(payload=[
            {"id": 5, "nombre": "PRESIDENCIA 1A VUELTA - 2026", "fecha": "2026-05-31"}
        ]),
        "GET /consultar/selecOganizacionPoliticaPublic": _FakeResp(payload={
            "organizaciones": [
                {"id": 9, "nombre": "PARTIDO X"},
            ]
        }),
    }
    sesion = _fake_session_factory(handlers)
    monkeypatch.setattr("ate.tools._cne_api.requests.Session", lambda: sesion)

    r = consultar_cne("Movimiento Inexistente", settings=_cfg())
    assert r.estado == "sin_datos"
    # Procesos 2026 deben venir como contexto disponible aunque no hubo match.
    assert any(item["tipo"] == "proceso_electoral" for item in r.resultados)


def test_consultar_cne_api_offline():
    cfg = _cfg(ate_offline=True)
    r = consultar_cne("Pacto", settings=cfg)
    assert r.estado == "offline"


def test_consultar_cne_api_red_caida(monkeypatch):
    import requests as _req
    handlers = {"GET /informes/cne": _FakeResp(payload=None)}
    sesion = _fake_session_factory(handlers)

    def fail_get(url, **kw):
        if "informes/cne" in url:
            return _FakeResp(payload=None)
        raise _req.exceptions.ConnectionError("network out")

    sesion.get = MagicMock(side_effect=fail_get)
    monkeypatch.setattr("ate.tools._cne_api.requests.Session", lambda: sesion)

    r = consultar_cne("Pacto", settings=_cfg())
    assert r.estado == "error_red"
    assert "API publica del CNE 2026" in r.mensaje


def test_consultar_cne_prioridad_dataset_socrata_por_encima_de_api(monkeypatch):
    """Si ATE_CNE_DATASET esta seteado, ignora el modo API."""
    cfg = _cfg(cne_dataset="abcd-1234")
    monkeypatch.setattr(
        "ate.tools._socrata.http_get_json",
        lambda *a, **k: [{"donante": "ACME", "monto": "1"}],
    )
    # Si el codigo intentara la API, esto fallaria — pero el guardian de
    # prioridad debe llegar a Socrata primero.
    r = consultar_cne("acme", settings=cfg)
    assert r.estado == "ok"
    assert r.resultados[0]["donante"] == "ACME"
