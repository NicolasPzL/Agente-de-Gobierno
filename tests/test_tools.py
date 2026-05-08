"""Tests del registro de tools y del esquema estable de sus salidas.

Sprint 2: las tools devuelven `ResultadoExtraccion` (no dict). Como la
suite corre en modo offline (`ATE_OFFLINE=1` desde conftest), las tools
que tocan la red devuelven `estado="offline"` aqui — eso valida la red
de seguridad y mantiene los tests deterministas. Los tests con HTTP
mockeado viven en `test_tools_apis.py`.
"""

from __future__ import annotations

import pytest

from ate.schemas.state import Intencion, ResultadoExtraccion
from ate.tools import listar, obtener, tools_para


def test_hay_al_menos_cinco_tools_registradas():
    # Sprint 1 definio 5 tools (datos_abiertos, secop, cne, rag_planes,
    # busqueda_noticias). Ese numero puede crecer, nunca bajar.
    assert len(listar()) >= 5


@pytest.mark.parametrize(
    "nombre",
    [
        "consultar_datos_abiertos",
        "consultar_secop",
        "consultar_cne",
        "buscar_plan_gobierno",
        "buscar_noticias",
    ],
)
def test_cada_tool_devuelve_resultado_extraccion(nombre):
    """En offline, todas las tools devuelven `ResultadoExtraccion` valido.

    El estado puede ser `offline`, `no_configurado` o `sin_datos` segun
    la tool — pero nunca `ok`, porque eso requeriria red.
    """
    spec = obtener(nombre)
    respuesta = spec.ejecutar("candidato de prueba")

    assert isinstance(respuesta, ResultadoExtraccion)
    assert respuesta.tool == nombre
    assert respuesta.consulta == "candidato de prueba"
    # Sin red, ningun call debe reportar 'ok'.
    assert respuesta.estado != "ok"
    # Cualquier estado valido del enum.
    assert respuesta.estado in {
        "offline",
        "no_configurado",
        "sin_datos",
        "error_red",
        "error_http",
        "error_parseo",
    }


@pytest.mark.parametrize(
    "intencion",
    [
        Intencion.DATOS_OFICIALES,
        Intencion.CONTRATACION,
        Intencion.FINANCIACION,
        Intencion.PLAN_GOBIERNO,
        Intencion.NOTICIAS,
    ],
)
def test_cada_intencion_operacional_tiene_al_menos_una_tool(intencion):
    assert tools_para(intencion), f"sin tools registradas para {intencion}"


def test_intencion_indefinida_no_propone_tools():
    assert tools_para(Intencion.INDEFINIDA) == []


def test_obtener_tool_inexistente_lanza_keyerror():
    with pytest.raises(KeyError):
        obtener("tool_que_no_existe")


def test_sprint_real_declarado_es_razonable():
    # En Sprint 2 las tools reales de extraccion ya son sprint_real=2.
    # La de RAG sigue en sprint_real=3.
    for spec in listar():
        assert spec.sprint_real >= 2, f"{spec.nombre} debe ser sprint_real >= 2"


def test_resultado_extraccion_tiene_urls_oficiales_o_estado_explicito():
    """Refuerza el principio de trazabilidad.

    Toda respuesta `ok` debe tener al menos una URL oficial (para
    citacion del Sprint 5). En estados no-ok puede no haberla.
    """
    for spec in listar():
        r = spec.ejecutar("petro")
        if r.estado == "ok":
            assert r.urls_oficiales, f"{spec.nombre}: ok sin urls_oficiales"
