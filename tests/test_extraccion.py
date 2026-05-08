"""Tests del agente de extraccion (Sprint 2).

Verifican:
    - El extractor invoca todas las tools listadas en el plan,
    - Maneja excepciones inesperadas devolviendo estado `error_*`,
    - Ignora intencion `INDEFINIDA` sin tocar nada,
    - Limita el numero de tools a `extraccion_max_tools`,
    - Coerciona dicts legacy a `ResultadoExtraccion` cuando es posible,
    - Integra con el grafo end-to-end (planificador -> extraccion).
"""

from __future__ import annotations

from dataclasses import replace
from typing import List

import pytest

from ate.agents.extraccion import extraer
from ate.config.settings import load_settings
from ate.graph.builder import construir_grafo
from ate.schemas.state import (
    ContextoExtraido,
    Intencion,
    PlanEjecucion,
    ResultadoExtraccion,
)
from ate.tools.registry import ToolSpec, _REGISTRO, registrar


# ---------- Fixtures de tools fake registradas ad-hoc para los tests ----------


def _hacer_tool_ok(nombre: str, fuente: str = "Fake API"):
    """Registra una tool fake que devuelve un ResultadoExtraccion ok."""
    def fn(consulta: str, *, settings=None) -> ResultadoExtraccion:  # noqa: ARG001
        return ResultadoExtraccion(
            fuente=fuente,
            tool=nombre,
            consulta=consulta,
            estado="ok",
            resultados=[{"a": 1}],
            total_resultados=1,
            urls_oficiales=[f"https://{nombre}.test/source"],
            mensaje=f"{nombre} ok",
        )
    spec = ToolSpec(
        nombre=nombre,
        descripcion=f"fake tool {nombre}",
        intenciones=(Intencion.NOTICIAS,),
        ejecutar=fn,
        sprint_real=2,
    )
    registrar(spec)
    return spec


def _hacer_tool_que_lanza(nombre: str):
    def fn(consulta: str, *, settings=None) -> ResultadoExtraccion:  # noqa: ARG001
        raise RuntimeError("kaboom")
    spec = ToolSpec(
        nombre=nombre,
        descripcion="fake tool que crashea",
        intenciones=(Intencion.NOTICIAS,),
        ejecutar=fn,
        sprint_real=2,
    )
    registrar(spec)
    return spec


def _hacer_tool_legacy_dict(nombre: str):
    """Tool que devuelve un dict (esquema Sprint 1) en lugar del Pydantic."""
    def fn(consulta: str, *, settings=None) -> dict:  # noqa: ARG001
        return {
            "fuente": "Legacy",
            "tool": nombre,
            "consulta": consulta,
            "estado": "ok",
            "resultados": [{"x": 1}],
            "total_resultados": 1,
            "urls_oficiales": [],
            "mensaje": "legacy",
        }
    spec = ToolSpec(
        nombre=nombre,
        descripcion="legacy",
        intenciones=(Intencion.NOTICIAS,),
        ejecutar=fn,  # type: ignore[arg-type]
        sprint_real=2,
    )
    registrar(spec)
    return spec


@pytest.fixture(autouse=True)
def _registro_aislado():
    """Snapshot del registro antes y restauracion despues de cada test.

    Sin esto, las tools fake se acumularian entre tests (el registro es
    un dict global por proceso).
    """
    snapshot = dict(_REGISTRO)
    yield
    _REGISTRO.clear()
    _REGISTRO.update(snapshot)


# ---------- Tests de la funcion extraer() ----------


def test_extractor_invoca_todas_las_tools_del_plan():
    _hacer_tool_ok("fake_a")
    _hacer_tool_ok("fake_b")
    plan = PlanEjecucion(
        intencion=Intencion.NOTICIAS,
        tools=["fake_a", "fake_b"],
        razonamiento="test",
    )

    contexto = extraer("una pregunta", plan)
    assert isinstance(contexto, ContextoExtraido)
    assert contexto.tools_invocadas == ["fake_a", "fake_b"]
    assert len(contexto.resultados) == 2
    assert all(r.estado == "ok" for r in contexto.resultados)


def test_extractor_con_intencion_indefinida_no_invoca_nada():
    _hacer_tool_ok("fake_x")
    plan = PlanEjecucion(intencion=Intencion.INDEFINIDA, tools=[])
    contexto = extraer("pregunta sin sentido", plan)
    assert contexto.tools_invocadas == []
    assert contexto.resultados == []


def test_extractor_traduce_excepcion_a_error_red():
    _hacer_tool_que_lanza("fake_boom")
    plan = PlanEjecucion(intencion=Intencion.NOTICIAS, tools=["fake_boom"])
    contexto = extraer("hola", plan)
    assert len(contexto.resultados) == 1
    r = contexto.resultados[0]
    assert r.estado == "error_red"
    assert "kaboom" in (r.error or "")


def test_extractor_marca_tool_no_registrada_como_error_parseo():
    plan = PlanEjecucion(
        intencion=Intencion.NOTICIAS,
        tools=["tool_inventada"],
    )
    contexto = extraer("hola", plan)
    assert "tool_inventada" in contexto.tools_omitidas
    assert contexto.resultados[0].estado == "error_parseo"


def test_extractor_coerciona_dict_legacy(caplog):
    _hacer_tool_legacy_dict("fake_legacy")
    plan = PlanEjecucion(intencion=Intencion.NOTICIAS, tools=["fake_legacy"])
    contexto = extraer("x", plan)
    r = contexto.resultados[0]
    assert isinstance(r, ResultadoExtraccion)
    assert r.estado == "ok"
    assert r.fuente == "Legacy"


def test_extractor_respeta_extraccion_max_tools():
    _hacer_tool_ok("a")
    _hacer_tool_ok("b")
    _hacer_tool_ok("c")
    settings = replace(load_settings(), extraccion_max_tools=2, ate_offline=False)
    plan = PlanEjecucion(
        intencion=Intencion.NOTICIAS,
        tools=["a", "b", "c"],
    )
    contexto = extraer("hi", plan, settings=settings)
    assert contexto.tools_invocadas == ["a", "b"]
    assert contexto.tools_omitidas == ["c"]


# ---------- Tests del nodo en el grafo ----------


def test_grafo_pasa_por_extraccion_y_pone_contexto():
    grafo = construir_grafo()
    final = grafo.invoke({"pregunta": "¿Que contratos tiene en SECOP?"})
    assert "contexto_extraido" in final
    contexto = final["contexto_extraido"]
    assert isinstance(contexto, ContextoExtraido)
    # Sin red, el resultado debe ser estado offline (ATE_OFFLINE=1 desde conftest).
    assert "consultar_secop" in contexto.tools_invocadas
    assert contexto.resultados[0].estado == "offline"


def test_grafo_indefinida_produce_contexto_vacio():
    grafo = construir_grafo()
    final = grafo.invoke({"pregunta": "Hola, como estas"})
    assert final["plan"].intencion is Intencion.INDEFINIDA
    contexto = final["contexto_extraido"]
    assert contexto.tools_invocadas == []
    assert contexto.resultados == []


def test_grafo_extraccion_tras_planificador_para_financiacion():
    grafo = construir_grafo()
    final = grafo.invoke({"pregunta": "Donantes en Cuentas Claras"})
    assert final["plan"].intencion is Intencion.FINANCIACION
    contexto = final["contexto_extraido"]
    assert "consultar_cne" in contexto.tools_invocadas
    # CNE en defaults vacios y offline -> offline gana porque la verificacion
    # offline esta dentro del cliente HTTP; pero CNE corta antes con
    # no_configurado si dataset/csv vacios. Verificamos uno de los dos.
    estado = contexto.resultados[0].estado
    assert estado in {"no_configurado", "offline"}
