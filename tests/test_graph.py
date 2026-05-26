"""Tests del grafo LangGraph - Sprint 4.

Verifica que el grafo compile, ejecute todos los nodos y que los campos
del estado final sean correctos. En modo offline (conftest) los nodos de
extraccion y RAG devuelven estados 'offline'/'no_configurado'; contraste
y validador operan sobre esos datos vacios y deben declarar ausencia sin
errores.
"""

from __future__ import annotations

import pytest

from ate.graph.builder import construir_grafo
from ate.schemas.state import (
    ContextoContraste,
    ContextoValidacion,
    Intencion,
    PlanEjecucion,
)


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


# ---------------------------------------------------------------------------
# Sprint 4: nodos contraste y validador
# ---------------------------------------------------------------------------


def test_grafo_sprint4_produce_contraste():
    """El grafo Sprint 4 siempre llena el campo 'contraste'."""
    grafo = construir_grafo()
    final = grafo.invoke({"pregunta": "Sanciones de Ivan Cepeda"})
    assert "contraste" in final
    assert isinstance(final["contraste"], ContextoContraste)


def test_grafo_sprint4_produce_validacion():
    """El grafo Sprint 4 siempre llena el campo 'validacion'."""
    grafo = construir_grafo()
    final = grafo.invoke({"pregunta": "Sanciones de Ivan Cepeda"})
    assert "validacion" in final
    assert isinstance(final["validacion"], ContextoValidacion)


def test_grafo_sprint4_contraste_estado_valido():
    """El campo contraste tiene un estado reconocido."""
    grafo = construir_grafo()
    final = grafo.invoke({"pregunta": "¿Que contratos tiene Ivan Cepeda?"})
    estado = final["contraste"].estado
    assert estado in {"ok", "sin_datos", "sin_candidato", "error"}


def test_grafo_sprint4_validacion_estado_valido():
    """El campo validacion tiene un estado reconocido."""
    grafo = construir_grafo()
    final = grafo.invoke({"pregunta": "¿Que propone Claudia Lopez?"})
    estado = final["validacion"].estado
    assert estado in {"ok", "offline", "sin_fuentes"}


def test_grafo_sprint4_sin_candidato_contraste_sin_candidato():
    """Pregunta sin candidato -> contraste.estado == 'sin_candidato'."""
    grafo = construir_grafo()
    final = grafo.invoke({"pregunta": "¿Que contratos hay en SECOP?"})
    # Puede que no detecte candidato; si no, el contraste debe declararlo
    contraste = final["contraste"]
    if contraste.candidato_id is None:
        assert contraste.estado == "sin_candidato"


def test_grafo_sprint4_no_inventa_inconsistencias_en_offline():
    """En modo offline no hay datos reales; el contraste no debe inventar."""
    grafo = construir_grafo()
    final = grafo.invoke({"pregunta": "Sanciones de Ivan Cepeda"})
    contraste = final["contraste"]
    # En offline, no hay datos para generar inconsistencias reales.
    # El sistema debe declarar sin_datos o no tener inconsistencias inventadas.
    if contraste.estado == "ok":
        # Si ejecuto el contraste, las inconsistencias deben basarse en datos reales
        for inc in contraste.inconsistencias:
            assert inc.tipo in {
                "propuesta_sin_contratos",
                "contratos_sin_propuesta",
                "sanciones_detectadas",
                "inconsistencia_sectorial",
            }
    else:
        assert contraste.estado in {"sin_datos", "sin_candidato"}
