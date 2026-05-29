"""Tests de las tools del Sprint 2 con HTTP mockeado.

Estos tests NO tocan la red:
    - se monkeypatchea `ate.tools._http.http_get_json` y `http_post_json`,
    - se monkeypatchea `requests.get` para el camino CSV de Cuentas Claras,
    - el flag `ATE_OFFLINE=1` esta activo desde `conftest.py` como red
      de seguridad: si un monkeypatch fuera incompleto, la tool igual
      cortaria antes de salir a internet.

Cada bloque verifica:
    - estado=`ok` con resultados normalizados,
    - estado=`error_*` ante fallo del backend,
    - estado=`no_configurado` cuando faltan keys / datasets,
    - urls_oficiales presentes para citacion del Sprint 5.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
import requests

from ate.config.settings import Settings, load_settings
from ate.schemas.state import ResultadoExtraccion
from ate.tools import _http
from ate.tools.busqueda_noticias import buscar_noticias
from ate.tools.cne import consultar_cne
from ate.tools.datos_abiertos import consultar_datos_abiertos
from ate.tools.secop import consultar_secop


def _settings_online(**overrides: Any) -> Settings:
    """Settings con red habilitada (sobreescribe el ATE_OFFLINE del conftest).

    Default: `ate_offline=False`. Se puede sobreescribir pasando
    `ate_offline=True` en `overrides` para tests que verifiquen el
    comportamiento offline explicitamente.
    """
    base = load_settings()
    overrides.setdefault("ate_offline", False)
    return replace(base, **overrides)


# ----------------------------------------------------------------------
# datos_abiertos
# ----------------------------------------------------------------------


def test_datos_abiertos_ok(monkeypatch):
    cfg = _settings_online()
    filas_mock = [
        {"nombre": "PEREZ JUAN", "tipo_sancion": "Inhabilidad", "anos": "10"},
        {"nombre": "PEREZ JUAN", "tipo_sancion": "Multa", "anos": "1"},
    ]

    def fake_get_json(url, *, settings, params, headers=None, timeout=None, socrata=False):  # noqa: ARG001
        assert "/resource/" in url
        assert params["$q"] == "petro"
        return filas_mock

    monkeypatch.setattr("ate.tools._socrata.http_get_json", fake_get_json)

    r = consultar_datos_abiertos("petro", settings=cfg)
    assert isinstance(r, ResultadoExtraccion)
    assert r.estado == "ok"
    assert r.total_resultados == 2
    assert r.resultados == filas_mock
    assert r.urls_oficiales and r.urls_oficiales[0].startswith("https://")
    assert r.tool == "consultar_datos_abiertos"


def test_datos_abiertos_sin_datos(monkeypatch):
    cfg = _settings_online()
    monkeypatch.setattr("ate.tools._socrata.http_get_json", lambda *a, **k: [])
    r = consultar_datos_abiertos("xyz", settings=cfg)
    assert r.estado == "sin_datos"
    assert r.urls_oficiales


def test_datos_abiertos_error_http(monkeypatch):
    cfg = _settings_online()

    def fake(*a, **k):
        raise _http.HttpError(clase="http", detalle="500 Server Error", status=500, url="x")

    monkeypatch.setattr("ate.tools._socrata.http_get_json", fake)
    r = consultar_datos_abiertos("petro", settings=cfg)
    assert r.estado == "error_http"
    assert r.error and "500" in r.error


def test_datos_abiertos_offline_por_settings():
    cfg = _settings_online(ate_offline=True)
    r = consultar_datos_abiertos("petro", settings=cfg)
    assert r.estado == "offline"


def test_datos_abiertos_no_configurado_sin_dataset():
    cfg = _settings_online(sanciones_dataset="")
    r = consultar_datos_abiertos("petro", settings=cfg)
    assert r.estado == "no_configurado"
    assert "ATE_SANCIONES_DATASET" in r.mensaje


# ----------------------------------------------------------------------
# SECOP
# ----------------------------------------------------------------------


def test_secop_combina_secop_i_y_ii(monkeypatch):
    cfg = _settings_online()
    llamadas = []

    def fake(url, *, settings, params, headers=None, timeout=None, socrata=False):  # noqa: ARG001
        llamadas.append(url)
        if "jbjy-vk9h" in url:
            return [{"entidad": "ICBF", "valor": "100"}]
        if "f789-7hwg" in url:
            return [{"entidad": "MIN_SALUD", "valor": "50"}, {"entidad": "MIN_TRABAJO"}]
        return []

    monkeypatch.setattr("ate.tools._socrata.http_get_json", fake)
    r = consultar_secop("petro", settings=cfg)
    assert r.estado == "ok"
    assert r.total_resultados == 3
    sub_fuentes = {f.get("__sub_fuente__") for f in r.resultados}
    assert sub_fuentes == {"SECOP I", "SECOP II"}
    # Ambos datasets citados.
    assert len(r.urls_oficiales) == 2


def test_secop_secop_ii_falla_pero_secop_i_ok(monkeypatch):
    cfg = _settings_online()

    def fake(url, *, settings, params, headers=None, timeout=None, socrata=False):  # noqa: ARG001
        if "jbjy-vk9h" in url:
            raise _http.HttpError(clase="http", detalle="429", status=429, url=url)
        return [{"entidad": "X"}]

    monkeypatch.setattr("ate.tools._socrata.http_get_json", fake)
    r = consultar_secop("petro", settings=cfg)
    assert r.estado == "ok"
    assert r.total_resultados == 1
    assert "Errores parciales" in r.mensaje


def test_secop_ambos_fallan(monkeypatch):
    cfg = _settings_online()

    def fake(*a, **k):
        raise _http.HttpError(clase="red", detalle="timeout", url="x")

    monkeypatch.setattr("ate.tools._socrata.http_get_json", fake)
    r = consultar_secop("petro", settings=cfg)
    assert r.estado == "error_red"
    assert r.error and "SECOP II" in r.error and "SECOP I" in r.error


def test_secop_no_configurado():
    cfg = _settings_online(secop_ii_dataset="", secop_i_dataset="")
    r = consultar_secop("petro", settings=cfg)
    assert r.estado == "no_configurado"


def test_secop_offline():
    cfg = _settings_online(ate_offline=True)
    r = consultar_secop("petro", settings=cfg)
    # Secop solo corta temprano si la primera llamada cae offline; con
    # http mockeado se evalua en _socrata.consulta_socrata via _ensure_online.
    assert r.estado == "offline"


# ----------------------------------------------------------------------
# CNE
# ----------------------------------------------------------------------


def test_cne_no_configurado_si_se_apagan_los_3_modos():
    """Si se desactivan API, dataset y CSV, la tool declara no_configurado."""
    cfg = _settings_online(cne_use_api=False)  # ya tiene cne_dataset/cne_csv_url vacios
    r = consultar_cne("aportes campana", settings=cfg)
    assert r.estado == "no_configurado"
    assert "ATE_CNE" in r.mensaje


def test_cne_socrata_ok(monkeypatch):
    cfg = _settings_online(cne_dataset="abcd-1234")
    monkeypatch.setattr(
        "ate.tools._socrata.http_get_json",
        lambda *a, **k: [{"donante": "ACME", "monto": "1000000"}],
    )
    r = consultar_cne("acme", settings=cfg)
    assert r.estado == "ok"
    assert r.total_resultados == 1
    assert any("cnecuentasclaras" in u for u in r.urls_oficiales)


def test_cne_csv_filtra_por_consulta(monkeypatch):
    cfg = _settings_online(cne_csv_url="https://example.test/cne.csv")
    csv_text = "donante,monto,partido\nACME SAS,1000000,Verde\nFundacion X,500000,Centro\n"

    class FakeResp:
        status_code = 200
        text = csv_text

    monkeypatch.setattr("ate.tools.cne.requests.get", lambda *a, **k: FakeResp())
    r = consultar_cne("acme", settings=cfg)
    assert r.estado == "ok"
    assert r.total_resultados == 1
    assert r.resultados[0]["donante"] == "ACME SAS"


def test_cne_csv_sin_coincidencias(monkeypatch):
    cfg = _settings_online(cne_csv_url="https://example.test/cne.csv")
    csv_text = "donante,monto\nACME,100\n"

    class FakeResp:
        status_code = 200
        text = csv_text

    monkeypatch.setattr("ate.tools.cne.requests.get", lambda *a, **k: FakeResp())
    r = consultar_cne("xyz_no_existe", settings=cfg)
    assert r.estado == "sin_datos"


def test_cne_csv_http_error(monkeypatch):
    cfg = _settings_online(cne_csv_url="https://example.test/cne.csv")

    class FakeResp:
        status_code = 503
        text = "service unavailable"

    monkeypatch.setattr("ate.tools.cne.requests.get", lambda *a, **k: FakeResp())
    r = consultar_cne("acme", settings=cfg)
    assert r.estado == "error_http"


def test_cne_csv_request_exception(monkeypatch):
    cfg = _settings_online(cne_csv_url="https://example.test/cne.csv")

    def boom(*a, **k):
        raise requests.ConnectionError("dns fallo")

    monkeypatch.setattr("ate.tools.cne.requests.get", boom)
    r = consultar_cne("acme", settings=cfg)
    assert r.estado == "error_red"


# ----------------------------------------------------------------------
# Buscador de noticias
# ----------------------------------------------------------------------


def test_noticias_no_configurado_sin_key():
    cfg = _settings_online(news_provider="tavily", tavily_api_key=None)
    r = buscar_noticias("petro entrevista", settings=cfg)
    assert r.estado == "no_configurado"
    assert "TAVILY_API_KEY" in r.mensaje


def test_noticias_tavily_ok(monkeypatch):
    cfg = _settings_online(news_provider="tavily", tavily_api_key="t-key")
    payload = {
        "results": [
            {
                "title": "Petro habla de reforma",
                "url": "https://eltiempo.com/x",
                "content": "Snippet...",
                "published_date": "2026-04-15",
                "score": 0.9,
            }
        ]
    }

    def fake_post(url, *, settings, json_body, headers=None, timeout=None):  # noqa: ARG001
        assert url == "https://api.tavily.com/search"
        assert json_body["api_key"] == "t-key"
        # Ancla el pais (Colombia) y preserva el tema/consulta del usuario.
        assert "Colombia" in json_body["query"]
        assert "Petro entrevista" in json_body["query"]
        return payload

    monkeypatch.setattr("ate.tools.busqueda_noticias.http_post_json", fake_post)
    r = buscar_noticias("Petro entrevista", settings=cfg)
    assert r.estado == "ok"
    assert r.total_resultados == 1
    assert r.resultados[0]["url"] == "https://eltiempo.com/x"
    assert r.urls_oficiales == ["https://eltiempo.com/x"]


def test_noticias_serper_ok(monkeypatch):
    cfg = _settings_online(news_provider="serper", serper_api_key="s-key")
    payload = {
        "news": [
            {
                "title": "Hoy",
                "link": "https://semana.com/y",
                "snippet": "...",
                "date": "2026-04-12",
                "source": "Semana",
            }
        ]
    }

    def fake_post(url, *, settings, json_body, headers=None, timeout=None):  # noqa: ARG001
        assert url == "https://google.serper.dev/news"
        assert headers["X-API-KEY"] == "s-key"
        return payload

    monkeypatch.setattr("ate.tools.busqueda_noticias.http_post_json", fake_post)
    r = buscar_noticias("camilo romero", settings=cfg)
    assert r.estado == "ok"
    assert r.resultados[0]["fuente"] == "Semana"


def test_noticias_provider_none():
    cfg = _settings_online(news_provider="none")
    r = buscar_noticias("algo", settings=cfg)
    assert r.estado == "no_configurado"


def test_noticias_tavily_falla(monkeypatch):
    cfg = _settings_online(news_provider="tavily", tavily_api_key="x")

    def fake_post(*a, **k):
        raise _http.HttpError(clase="http", detalle="401 invalid key", status=401, url="x")

    monkeypatch.setattr("ate.tools.busqueda_noticias.http_post_json", fake_post)
    r = buscar_noticias("petro", settings=cfg)
    assert r.estado == "error_http"
    assert "401" in (r.error or "")


def test_noticias_consulta_vacia():
    cfg = _settings_online(news_provider="tavily", tavily_api_key="x")
    r = buscar_noticias("   ", settings=cfg)
    assert r.estado == "sin_datos"


# ----------------------------------------------------------------------
# Cliente HTTP en si
# ----------------------------------------------------------------------


def test_http_get_json_corta_offline():
    cfg = _settings_online(ate_offline=True)
    with pytest.raises(_http.HttpError) as ei:
        _http.http_get_json("https://example.test", settings=cfg)
    assert ei.value.clase == "offline"


def test_http_post_json_corta_offline():
    cfg = _settings_online(ate_offline=True)
    with pytest.raises(_http.HttpError) as ei:
        _http.http_post_json("https://example.test", settings=cfg)
    assert ei.value.clase == "offline"


def test_estado_desde_error_mapea_correctamente():
    e_red = _http.HttpError(clase="red", detalle="x")
    e_http = _http.HttpError(clase="http", detalle="x", status=500)
    e_par = _http.HttpError(clase="parseo", detalle="x")
    e_off = _http.HttpError(clase="offline", detalle="x")
    assert _http.estado_desde_error(e_red) == "error_red"
    assert _http.estado_desde_error(e_http) == "error_http"
    assert _http.estado_desde_error(e_par) == "error_parseo"
    assert _http.estado_desde_error(e_off) == "offline"
