"""Tests del grafo LangGraph del Sprint 1."""

from __future__ import annotations

import pytest

from ate.graph.builder import construir_grafo
from ate.schemas.state import Intencion, PlanEjecucion


def test_grafo_se_compila_sin_error():
    grafo = construir_grafo()
    assert grafo is not None


def test_grafo_produce_plan_para_contratacion():
    grafo = construir_grafo()
    final = grafo.invoke({"pregunta": "¿Que contratos tiene el candidato en SECOP?"})

    assert "plan" in final
    plan = final["plan"]
    assert isinstance(plan, PlanEjecucion)
    assert plan.intencion is Intencion.CONTRATACION
    assert "consultar_secop" in plan.tools


def test_grafo_preserva_pregunta():
    grafo = construir_grafo()
    pregunta = "¿Que propone en educacion?"
    final = grafo.invoke({"pregunta": pregunta})

    assert final.get("pregunta") == pregunta
    assert final["plan"].intencion is Intencion.PLAN_GOBIERNO


@pytest.mark.parametrize(
    "pregunta, intencion_esperada",
    [
        ("Sanciones del candidato", Intencion.DATOS_OFICIALES),
        ("Donantes registrados en Cuentas Claras", Intencion.FINANCIACION),
        ("Noticias recientes", Intencion.NOTICIAS),
        ("Hola, como estas", Intencion.INDEFINIDA),
    ],
)
def test_grafo_end_to_end_para_varias_intenciones(pregunta, intencion_esperada):
    grafo = construir_grafo()
    final = grafo.invoke({"pregunta": pregunta})
    assert final["plan"].intencion is intencion_esperada
