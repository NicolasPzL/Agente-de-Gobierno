"""Tests de la reescritura de consulta por tool en el extractor (Sprint 2.5)."""

from __future__ import annotations

import pytest

from ate.agents.extraccion import _TOOLS_DELEGADAS, consulta_para_tool, extraer
from ate.candidatos.registro import por_id
from ate.schemas.state import Intencion, PlanEjecucion


def test_sin_candidato_pasa_pregunta_cruda():
    for tool in ["consultar_secop", "consultar_cne", "buscar_noticias", "X"]:
        assert consulta_para_tool("la pregunta", None, tool) == "la pregunta"


def test_con_candidato_secop_recibe_canonico():
    cep = por_id("ivan-cepeda")
    assert consulta_para_tool("X", cep, "consultar_secop") == "Ivan Cepeda Castro"


def test_con_candidato_cne_recibe_partido():
    cep = por_id("ivan-cepeda")
    assert consulta_para_tool("X", cep, "consultar_cne") == "Pacto Historico"


def test_noticias_preserva_tema_y_ancla_nombre():
    """La consulta de noticias debe conservar el TEMA de la pregunta (p.ej.
    'polemicas') y anclar el nombre del candidato. Regresion: antes se
    reemplazaba por 'nombre + partido', borrando el tema."""
    cep = por_id("ivan-cepeda")
    q = consulta_para_tool("¿que polemicas tiene?", cep, "buscar_noticias")
    assert "Ivan Cepeda" in q
    assert "polemicas" in q


def test_noticias_no_duplica_nombre_si_ya_aparece():
    cep = por_id("ivan-cepeda")
    q = consulta_para_tool("noticias de Ivan Cepeda sobre la paz", cep, "buscar_noticias")
    assert q == "noticias de Ivan Cepeda sobre la paz"


def test_con_candidato_datos_oficiales_recibe_canonico():
    cep = por_id("ivan-cepeda")
    assert consulta_para_tool("X", cep, "consultar_datos_abiertos") == "Ivan Cepeda Castro"


def test_tool_desconocida_recibe_pregunta_original():
    cep = por_id("ivan-cepeda")
    assert consulta_para_tool("la pregunta", cep, "nueva_tool_x") == "la pregunta"


def test_extractor_omite_buscar_plan_gobierno():
    """El RAG vive en su nodo dedicado; el extractor no lo invoca."""
    cep = por_id("ivan-cepeda")
    plan = PlanEjecucion(
        intencion=Intencion.PLAN_GOBIERNO,
        tools=["buscar_plan_gobierno"],
        candidato=cep,
    )
    contexto = extraer("¿que propone?", plan)
    assert contexto.tools_invocadas == []
    assert "buscar_plan_gobierno" in contexto.tools_omitidas


def test_buscar_plan_gobierno_esta_en_tools_delegadas():
    assert "buscar_plan_gobierno" in _TOOLS_DELEGADAS
