"""Tests del agente validador - Sprint 4.

Todos los tests corren en modo offline (conftest fuerza ATE_OFFLINE=1).
En offline, el validador solo verifica el dominio y no toca la red;
`accesible` siempre es None. Los tests son 100% deterministicos.
"""

from __future__ import annotations

import pytest

from ate.agents.validador import (
    _es_dominio_oficial,
    _extraer_dominio,
    _recopilar_urls,
    nodo_validador,
    validar,
)
from ate.schemas.state import (
    ContextoExtraido,
    ContextoValidacion,
    ResultadoExtraccion,
)


# ---------------------------------------------------------------------------
# Fixtures reutilizables
# ---------------------------------------------------------------------------


def _resultado_con_urls(*urls: str, tool: str = "consultar_secop") -> ResultadoExtraccion:
    return ResultadoExtraccion(
        fuente="Fuente de test",
        tool=tool,
        consulta="test",
        estado="ok",
        resultados=[],
        total_resultados=0,
        urls_oficiales=list(urls),
        mensaje="",
    )


def _extraido_con_urls(*urls: str, tool: str = "consultar_secop") -> ContextoExtraido:
    return ContextoExtraido(
        consulta="test",
        tools_invocadas=[tool],
        tools_omitidas=[],
        resultados=[_resultado_con_urls(*urls, tool=tool)],
    )


# ---------------------------------------------------------------------------
# Tests de _extraer_dominio
# ---------------------------------------------------------------------------


class TestExtraerDominio:
    def test_url_con_www(self):
        assert _extraer_dominio("https://www.datos.gov.co/d/jbjy-vk9h") == "datos.gov.co"

    def test_url_sin_www(self):
        assert _extraer_dominio("https://datos.gov.co/d/jbjy-vk9h") == "datos.gov.co"

    def test_url_subdominio(self):
        assert _extraer_dominio("https://api.procuraduria.gov.co/sanciones") == "api.procuraduria.gov.co"

    def test_url_con_path_y_query(self):
        assert _extraer_dominio("https://cne.gov.co/consulta?id=1") == "cne.gov.co"

    def test_cadena_vacia(self):
        assert _extraer_dominio("") == ""

    def test_cadena_no_url(self):
        assert _extraer_dominio("no-es-una-url") == ""

    def test_http_sin_www(self):
        assert _extraer_dominio("http://contratacion.gov.co/index") == "contratacion.gov.co"


# ---------------------------------------------------------------------------
# Tests de _es_dominio_oficial
# ---------------------------------------------------------------------------


class TestEsDominioOficial:
    def test_datos_gov_co(self):
        assert _es_dominio_oficial("datos.gov.co") is True

    def test_procuraduria_gov_co(self):
        assert _es_dominio_oficial("procuraduria.gov.co") is True

    def test_cne_gov_co(self):
        assert _es_dominio_oficial("cne.gov.co") is True

    def test_subdominio_de_gov_co_es_oficial(self):
        assert _es_dominio_oficial("api.datos.gov.co") is True

    def test_cualquier_subdominio_gov_co(self):
        assert _es_dominio_oficial("mindefensa.gov.co") is True

    def test_rnec_org_co(self):
        assert _es_dominio_oficial("rnec.org.co") is True

    def test_dominio_comercial_no_oficial(self):
        assert _es_dominio_oficial("eltiempo.com") is False

    def test_semana_no_oficial(self):
        assert _es_dominio_oficial("semana.com") is False

    def test_facebook_no_oficial(self):
        assert _es_dominio_oficial("facebook.com") is False

    def test_dominio_vacio(self):
        assert _es_dominio_oficial("") is False

    def test_gov_co_exacto(self):
        assert _es_dominio_oficial("gov.co") is True

    def test_gov_co_con_subdominio_profundo(self):
        assert _es_dominio_oficial("datos.entidad.gov.co") is True


# ---------------------------------------------------------------------------
# Tests de _recopilar_urls
# ---------------------------------------------------------------------------


class TestRecopilarUrls:
    def test_recopila_urls_del_contexto(self):
        extraido = _extraido_con_urls(
            "https://www.datos.gov.co/d/jbjy-vk9h",
            "https://www.datos.gov.co/d/f789-7hwg",
        )
        urls = _recopilar_urls(extraido)
        assert len(urls) == 2

    def test_deduplica_urls_repetidas(self):
        extraido = ContextoExtraido(
            consulta="test",
            tools_invocadas=["consultar_secop"],
            tools_omitidas=[],
            resultados=[
                _resultado_con_urls(
                    "https://www.datos.gov.co/d/jbjy-vk9h",
                    "https://www.datos.gov.co/d/jbjy-vk9h",  # duplicado
                )
            ],
        )
        urls = _recopilar_urls(extraido)
        assert len(urls) == 1

    def test_contexto_none_retorna_lista_vacia(self):
        assert _recopilar_urls(None) == []

    def test_sin_resultados_retorna_lista_vacia(self):
        extraido = ContextoExtraido(
            consulta="test",
            tools_invocadas=[],
            tools_omitidas=[],
            resultados=[],
        )
        assert _recopilar_urls(extraido) == []

    def test_urls_vacias_se_omiten(self):
        extraido = ContextoExtraido(
            consulta="test",
            tools_invocadas=["consultar_secop"],
            tools_omitidas=[],
            resultados=[_resultado_con_urls("", "https://datos.gov.co")],
        )
        urls = _recopilar_urls(extraido)
        assert len(urls) == 1
        assert "" not in urls

    def test_deduplica_entre_multiples_resultados(self):
        url_comun = "https://www.datos.gov.co/d/jbjy-vk9h"
        extraido = ContextoExtraido(
            consulta="test",
            tools_invocadas=["consultar_secop", "consultar_datos_abiertos"],
            tools_omitidas=[],
            resultados=[
                _resultado_con_urls(url_comun, tool="consultar_secop"),
                _resultado_con_urls(url_comun, tool="consultar_datos_abiertos"),
            ],
        )
        urls = _recopilar_urls(extraido)
        assert len(urls) == 1


# ---------------------------------------------------------------------------
# Tests de la funcion principal `validar`
# ---------------------------------------------------------------------------


class TestValidarOffline:
    """En conftest, ATE_OFFLINE=1 siempre. Todos estos tests son offline."""

    def test_sin_contexto_retorna_sin_fuentes(self):
        resultado = validar(None, None)
        assert resultado.estado == "sin_fuentes"

    def test_url_oficial_cuenta_como_oficial(self):
        extraido = _extraido_con_urls("https://www.datos.gov.co/d/jbjy-vk9h")
        resultado = validar(extraido, None)
        assert resultado.fuentes_oficiales == 1
        assert resultado.fuentes_no_oficiales == 0

    def test_url_no_oficial_cuenta_como_no_oficial(self):
        extraido = _extraido_con_urls("https://www.semana.com/articulo/123")
        resultado = validar(extraido, None)
        assert resultado.fuentes_no_oficiales == 1
        assert resultado.fuentes_oficiales == 0

    def test_accesible_es_none_en_offline(self):
        extraido = _extraido_con_urls("https://www.datos.gov.co/d/jbjy-vk9h")
        resultado = validar(extraido, None)
        for fuente in resultado.fuentes_validadas:
            assert fuente.accesible is None

    def test_estado_offline_cuando_modo_offline(self):
        extraido = _extraido_con_urls("https://www.datos.gov.co/d/jbjy-vk9h")
        resultado = validar(extraido, None)
        assert resultado.estado == "offline"

    def test_total_fuentes_correcto(self):
        extraido = _extraido_con_urls(
            "https://www.datos.gov.co/d/jbjy-vk9h",
            "https://www.datos.gov.co/d/f789-7hwg",
            "https://www.datos.gov.co/d/iaeu-rcn6",
        )
        resultado = validar(extraido, None)
        assert resultado.total_fuentes == 3

    def test_mixto_oficial_y_no_oficial(self):
        extraido = ContextoExtraido(
            consulta="test",
            tools_invocadas=["consultar_secop", "buscar_noticias"],
            tools_omitidas=[],
            resultados=[
                _resultado_con_urls("https://www.datos.gov.co/d/jbjy-vk9h", tool="consultar_secop"),
                _resultado_con_urls("https://www.semana.com/articulo/1", tool="buscar_noticias"),
            ],
        )
        resultado = validar(extraido, None)
        assert resultado.fuentes_oficiales == 1
        assert resultado.fuentes_no_oficiales == 1
        assert resultado.total_fuentes == 2

    def test_dominio_detectado_en_fuente(self):
        extraido = _extraido_con_urls("https://www.datos.gov.co/d/jbjy-vk9h")
        resultado = validar(extraido, None)
        assert resultado.fuentes_validadas[0].dominio_detectado == "datos.gov.co"

    def test_propiedad_todas_oficiales_true(self):
        extraido = _extraido_con_urls(
            "https://www.datos.gov.co/d/jbjy-vk9h",
            "https://procuraduria.gov.co/siri",
        )
        resultado = validar(extraido, None)
        assert resultado.todas_oficiales is True

    def test_propiedad_todas_oficiales_false_con_no_oficial(self):
        extraido = ContextoExtraido(
            consulta="test",
            tools_invocadas=["buscar_noticias"],
            tools_omitidas=[],
            resultados=[
                _resultado_con_urls(
                    "https://datos.gov.co",
                    "https://notoficial.com",
                    tool="buscar_noticias",
                )
            ],
        )
        resultado = validar(extraido, None)
        assert resultado.todas_oficiales is False

    def test_todas_oficiales_false_sin_fuentes(self):
        resultado = validar(None, None)
        assert resultado.todas_oficiales is False

    def test_inaccesibles_es_cero_en_offline(self):
        # En offline accesible=None, no False; por tanto inaccesibles=0
        extraido = _extraido_con_urls("https://www.datos.gov.co/d/jbjy-vk9h")
        resultado = validar(extraido, None)
        assert resultado.fuentes_inaccesibles == 0

    def test_observacion_menciona_dominio(self):
        extraido = _extraido_con_urls("https://www.datos.gov.co/d/jbjy-vk9h")
        resultado = validar(extraido, None)
        assert "datos.gov.co" in resultado.fuentes_validadas[0].observacion

    def test_url_no_oficial_observacion_lo_indica(self):
        extraido = _extraido_con_urls("https://www.facebook.com/candidato")
        resultado = validar(extraido, None)
        fuente = resultado.fuentes_validadas[0]
        assert not fuente.es_oficial
        assert "no" in fuente.observacion.lower() or "no pertenece" in fuente.observacion.lower()


# ---------------------------------------------------------------------------
# Tests del nodo LangGraph
# ---------------------------------------------------------------------------


class TestNodoValidador:
    def test_retorna_campo_validacion(self):
        estado = {
            "pregunta": "test",
            "contexto_extraido": None,
            "contexto_rag": None,
        }
        resultado = nodo_validador(estado)
        assert "validacion" in resultado

    def test_sin_contexto_estado_sin_fuentes(self):
        estado = {
            "pregunta": "test",
            "contexto_extraido": None,
            "contexto_rag": None,
        }
        resultado = nodo_validador(estado)
        assert resultado["validacion"].estado == "sin_fuentes"

    def test_con_urls_retorna_estado_valido(self):
        extraido = _extraido_con_urls("https://www.datos.gov.co/d/jbjy-vk9h")
        estado = {
            "pregunta": "test",
            "contexto_extraido": extraido,
            "contexto_rag": None,
        }
        resultado = nodo_validador(estado)
        assert resultado["validacion"].estado in {"ok", "offline", "sin_fuentes"}
        assert resultado["validacion"].total_fuentes == 1

    def test_retorna_instancia_correcta(self):
        estado = {
            "pregunta": "test",
            "contexto_extraido": None,
            "contexto_rag": None,
        }
        resultado = nodo_validador(estado)
        assert isinstance(resultado["validacion"], ContextoValidacion)
