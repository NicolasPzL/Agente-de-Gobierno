"""Tests del registro de tools y del esquema estable de sus stubs."""

from __future__ import annotations

import pytest

from ate.schemas.state import Intencion
from ate.tools import listar, obtener, tools_para


_CAMPOS_RESPUESTA = ("fuente", "estado", "consulta", "resultados", "mensaje")


def test_hay_al_menos_cinco_tools_registradas():
    # Sprint 1 define exactamente 5 stubs (datos_abiertos, secop, cne,
    # rag_planes, busqueda_noticias). Ese numero puede crecer, nunca bajar.
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
def test_cada_tool_stub_respeta_esquema(nombre):
    spec = obtener(nombre)
    respuesta = spec.ejecutar("candidato de prueba")
    for campo in _CAMPOS_RESPUESTA:
        assert campo in respuesta, f"falta campo '{campo}' en {nombre}"
    assert respuesta["estado"] == "stub"
    assert isinstance(respuesta["resultados"], list)
    assert respuesta["consulta"] == "candidato de prueba"


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
    # Cada tool declara en que sprint deja de ser stub. Sprint 1 no
    # deberia contener tools "reales"; todas apuntan a >= 2.
    for spec in listar():
        assert spec.sprint_real >= 2, f"{spec.nombre} deberia esperar al Sprint 2 o posterior"
