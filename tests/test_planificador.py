"""Tests del agente planificador (camino determinista y Ollama mockeado)."""

from __future__ import annotations

import io
import json
from dataclasses import replace

import pytest

from ate.agents.planificador import (
    _invocar_llm_ollama,
    _normalizar,
    clasificar_por_palabras,
    planificar,
)
from ate.config.settings import Settings, load_settings
from ate.schemas.state import Intencion


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿De que origen proviene y cuanta plata tiene Cepeda para su campana?",
        "cuanto dinero tiene la campana de Fajardo",
        "quienes son los donantes de la campana",
        "de donde salen los fondos de Claudia Lopez",
        "como se financia Paloma Valencia",
        "patrimonio declarado del candidato",
    ],
)
def test_financiacion_reconoce_lenguaje_coloquial(pregunta):
    """Preguntas de financiación en lenguaje natural deben ser FINANCIACION,
    no INDEFINIDA (regresion: 'plata/dinero/fondos/financ' no se reconocian)."""
    intencion, _ = clasificar_por_palabras(pregunta)
    assert intencion is Intencion.FINANCIACION


def test_propuesta_en_campana_sigue_siendo_plan_gobierno():
    """'campana' es ambiguo: una pregunta sobre propuestas NO debe caer en
    FINANCIACION solo por mencionar la campana."""
    intencion, _ = clasificar_por_palabras("que propone en su campana sobre salud")
    assert intencion is Intencion.PLAN_GOBIERNO


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿que polemicas tiene Cepeda?",
        "escandalos recientes del candidato",
        "controversias de Fajardo",
        "ultima declaracion de Petro",
        "que noticias hay de Claudia Lopez",
        "denuncias contra el candidato",
        "que dijo el candidato esta semana",
    ],
)
def test_noticias_y_polemicas_se_clasifican_como_noticias(pregunta):
    """Regresion: las keywords de NOTICIAS tenian typos ('declcion',
    'declaracioaranes') y faltaban polemica/escandalo/controversia/denuncia."""
    intencion, _ = clasificar_por_palabras(pregunta)
    assert intencion is Intencion.NOTICIAS


def _settings_sin_llm() -> Settings:
    """Settings que fuerza el camino determinista (no toca red).

    Se construye sobre `load_settings()` para heredar todos los campos
    nuevos del Sprint 2 (Socrata, news_provider, etc.) sin tener que
    repetirlos aqui — solo se sobreescribe lo que el test necesita.
    """
    return replace(
        load_settings(),
        llm_provider="none",
        anthropic_api_key=None,
        openai_api_key=None,
        ollama_model="llama3.2:3b",
    )


@pytest.mark.parametrize(
    "pregunta, esperado",
    [
        ("¿Que contratos tiene el candidato en SECOP?", Intencion.CONTRATACION),
        ("Ver licitaciones del candidato", Intencion.CONTRATACION),
        ("Cuentas Claras del candidato X", Intencion.FINANCIACION),
        ("¿Quienes son sus donantes de campana?", Intencion.FINANCIACION),
        ("¿Tiene sanciones disciplinarias?", Intencion.DATOS_OFICIALES),
        ("Antecedentes penales del candidato", Intencion.DATOS_OFICIALES),
        ("¿Cual es su plan de gobierno en educacion?", Intencion.PLAN_GOBIERNO),
        ("¿Que propone sobre salud?", Intencion.PLAN_GOBIERNO),
        ("¿Que declaro ayer en la entrevista?", Intencion.NOTICIAS),
        ("Noticias recientes del candidato", Intencion.NOTICIAS),
        ("Hola", Intencion.INDEFINIDA),
        ("¿Como estas?", Intencion.INDEFINIDA),
    ],
)
def test_clasificar_por_palabras_detecta_intencion(pregunta, esperado):
    intencion, razon = clasificar_por_palabras(pregunta)
    assert intencion is esperado
    assert razon  # el razonamiento nunca debe quedar vacio


def test_clasificar_es_insensible_a_tildes_y_mayusculas():
    i1, _ = clasificar_por_palabras("¿Cuál es el PLAN DE GOBIERNO?")
    i2, _ = clasificar_por_palabras("cual es el plan de gobierno")
    assert i1 is i2 is Intencion.PLAN_GOBIERNO


def test_planificar_vacio_es_indefinida_sin_tools():
    plan = planificar("", settings=_settings_sin_llm())
    assert plan.intencion is Intencion.INDEFINIDA
    assert plan.tools == []
    assert "vac" in plan.razonamiento.lower()


def test_planificar_asocia_tool_secop_a_contratacion():
    plan = planificar(
        "¿Que contratos tiene el candidato?", settings=_settings_sin_llm()
    )
    assert plan.intencion is Intencion.CONTRATACION
    assert "consultar_secop" in plan.tools


def test_planificar_asocia_tool_cne_a_financiacion():
    plan = planificar(
        "¿Cuales son sus donantes en Cuentas Claras?", settings=_settings_sin_llm()
    )
    assert plan.intencion is Intencion.FINANCIACION
    assert "consultar_cne" in plan.tools


def test_planificar_asocia_tool_rag_a_plan_de_gobierno():
    plan = planificar(
        "¿Que propone en materia de educacion?", settings=_settings_sin_llm()
    )
    assert plan.intencion is Intencion.PLAN_GOBIERNO
    assert "buscar_plan_gobierno" in plan.tools


def test_indefinida_no_propone_tools():
    plan = planificar("blablabla texto sin sentido", settings=_settings_sin_llm())
    assert plan.intencion is Intencion.INDEFINIDA
    assert plan.tools == []


def test_planificar_es_determinista_sin_llm():
    cfg = _settings_sin_llm()
    p1 = planificar("¿Que contratos tiene el candidato?", settings=cfg)
    p2 = planificar("¿Que contratos tiene el candidato?", settings=cfg)
    assert p1.model_dump() == p2.model_dump()


def test_normalizar_quita_diacriticos():
    assert _normalizar("ÁÉÍÓÚñÑ") == "aeiounn"


# --- Camino Ollama (mockeando urllib, no toca red) ---


class _RespuestaFake:
    """Context manager que imita `urllib.request.urlopen(...)`."""

    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return io.BytesIO(self._body)

    def __exit__(self, *a):
        return False


def test_ollama_parsea_respuesta_estructurada(monkeypatch):
    cfg = replace(_settings_sin_llm(), llm_provider="ollama")
    respuesta_mock = {
        "response": json.dumps(
            {"intencion": "contratacion", "razonamiento": "Menciona SECOP."}
        )
    }

    def fake_urlopen(request, timeout):  # noqa: ARG001
        assert request.full_url.endswith("/api/generate")
        enviado = json.loads(request.data.decode("utf-8"))
        assert enviado["model"] == cfg.ollama_model
        assert enviado["format"] == "json"
        assert "prompt" in enviado and isinstance(enviado["prompt"], str)
        return _RespuestaFake(respuesta_mock)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    intencion, razonamiento = _invocar_llm_ollama("¿contratos en SECOP?", cfg)
    assert intencion is Intencion.CONTRATACION
    assert razonamiento == "Menciona SECOP."


def test_ollama_intencion_invalida_lanza_runtimeerror(monkeypatch):
    cfg = replace(_settings_sin_llm(), llm_provider="ollama")
    respuesta_mock = {
        "response": json.dumps({"intencion": "no_existe", "razonamiento": "x"})
    }
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout: _RespuestaFake(respuesta_mock),  # noqa: ARG005
    )
    with pytest.raises(RuntimeError, match="Intencion invalida"):
        _invocar_llm_ollama("algo", cfg)


def test_ollama_provider_mal_configurado_lanza_runtimeerror():
    with pytest.raises(RuntimeError, match="no es 'ollama'"):
        _invocar_llm_ollama("x", _settings_sin_llm())
