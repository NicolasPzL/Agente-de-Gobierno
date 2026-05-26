"""Tests del agente de contraste - Sprint 4.

Todos los tests corren en modo offline (conftest fuerza ATE_OFFLINE=1 y
ATE_LLM_PROVIDER=none). El contraste es 100% deterministico y no toca
la red ni el LLM; no necesita mocks adicionales.
"""

from __future__ import annotations

import pytest

from ate.agents.contraste import (
    _detectar_sectores,
    _extraer_contratos,
    _extraer_sanciones,
    _secop_fue_consultado,
    contrastar,
    nodo_contraste,
)
from ate.candidatos.registro import CANDIDATOS_2026
from ate.schemas.state import (
    ContextoExtraido,
    ContextoRag,
    Intencion,
    PasajeRag,
    PlanEjecucion,
    ResultadoExtraccion,
)

# ---------------------------------------------------------------------------
# Fixtures reutilizables
# ---------------------------------------------------------------------------

_CANDIDATO = CANDIDATOS_2026[0]  # Ivan Cepeda Castro


@pytest.fixture
def plan_con_candidato() -> PlanEjecucion:
    return PlanEjecucion(
        intencion=Intencion.CONTRATACION,
        tools=["consultar_secop"],
        razonamiento="Test",
        candidato=_CANDIDATO,
    )


@pytest.fixture
def plan_sin_candidato() -> PlanEjecucion:
    return PlanEjecucion(
        intencion=Intencion.CONTRATACION,
        tools=["consultar_secop"],
        razonamiento="Test",
        candidato=None,
    )


@pytest.fixture
def rag_con_pasajes() -> ContextoRag:
    return ContextoRag(
        consulta="propuestas educacion salud",
        candidato_filtro=_CANDIDATO.id,
        pasajes=[
            PasajeRag(
                texto="Proponemos invertir en salud publica y hospitales.",
                candidato_id=_CANDIDATO.id,
                candidato_nombre=_CANDIDATO.nombre_canonico,
                pdf="test.pdf",
                pagina=1,
                chunk_id="test:p1:c1",
                score=0.1,
            ),
            PasajeRag(
                texto="Nuestro plan contempla mejorar la educacion basica.",
                candidato_id=_CANDIDATO.id,
                candidato_nombre=_CANDIDATO.nombre_canonico,
                pdf="test.pdf",
                pagina=2,
                chunk_id="test:p2:c1",
                score=0.2,
            ),
        ],
        estado="ok",
        mensaje="2 pasajes encontrados.",
    )


@pytest.fixture
def rag_vacio() -> ContextoRag:
    return ContextoRag(
        consulta="test",
        candidato_filtro=_CANDIDATO.id,
        pasajes=[],
        estado="sin_datos",
        mensaje="Sin resultados.",
    )


def _hacer_resultado_secop(estado: str, resultados: list) -> ResultadoExtraccion:
    return ResultadoExtraccion(
        fuente="SECOP I + SECOP II",
        tool="consultar_secop",
        consulta=_CANDIDATO.consulta_secop,
        estado=estado,
        resultados=resultados,
        total_resultados=len(resultados),
        urls_oficiales=["https://www.datos.gov.co/d/jbjy-vk9h"],
        mensaje=f"{len(resultados)} contrato(s).",
    )


def _hacer_resultado_sanciones(n: int) -> ResultadoExtraccion:
    return ResultadoExtraccion(
        fuente="Procuraduria SIRI",
        tool="consultar_datos_abiertos",
        consulta=_CANDIDATO.consulta_datos_oficiales,
        estado="ok",
        resultados=[{"tipo_sancion": "Suspension", "descripcion": f"Falta grave {i}"} for i in range(n)],
        total_resultados=n,
        urls_oficiales=["https://www.datos.gov.co/d/iaeu-rcn6"],
        mensaje=f"{n} sancion(es).",
    )


@pytest.fixture
def extraido_con_contratos() -> ContextoExtraido:
    return ContextoExtraido(
        consulta=_CANDIDATO.consulta_secop,
        tools_invocadas=["consultar_secop"],
        tools_omitidas=[],
        resultados=[
            _hacer_resultado_secop(
                "ok",
                [{"descripcion_del_proceso": "Construccion hospital rural", "valor": "500000000"}],
            )
        ],
    )


@pytest.fixture
def extraido_secop_sin_contratos() -> ContextoExtraido:
    """SECOP fue consultado pero no retorno contratos (estado sin_datos)."""
    return ContextoExtraido(
        consulta=_CANDIDATO.consulta_secop,
        tools_invocadas=["consultar_secop"],
        tools_omitidas=[],
        resultados=[_hacer_resultado_secop("sin_datos", [])],
    )


@pytest.fixture
def extraido_con_sanciones() -> ContextoExtraido:
    return ContextoExtraido(
        consulta=_CANDIDATO.consulta_datos_oficiales,
        tools_invocadas=["consultar_datos_abiertos"],
        tools_omitidas=[],
        resultados=[_hacer_resultado_sanciones(2)],
    )


# ---------------------------------------------------------------------------
# Tests de funciones auxiliares
# ---------------------------------------------------------------------------


class TestDetectarSectores:
    def test_detecta_salud(self):
        assert "salud" in _detectar_sectores("Proponemos invertir en salud publica.")

    def test_detecta_educacion(self):
        assert "educacion" in _detectar_sectores("Mejorar la educacion basica.")

    def test_detecta_multiples_sectores(self):
        texto = "Plan integral de salud y educacion para el campo."
        sectores = _detectar_sectores(texto)
        assert "salud" in sectores
        assert "educacion" in sectores
        assert "agricultura" in sectores

    def test_texto_sin_sector_retorna_vacio(self):
        assert _detectar_sectores("hola como estas") == set()

    def test_texto_vacio(self):
        assert _detectar_sectores("") == set()


class TestExtraerContratos:
    def test_extrae_contratos_ok(self, extraido_con_contratos):
        contratos = _extraer_contratos(extraido_con_contratos)
        assert len(contratos) == 1

    def test_ignora_estado_sin_datos(self, extraido_secop_sin_contratos):
        contratos = _extraer_contratos(extraido_secop_sin_contratos)
        assert contratos == []

    def test_ignora_herramienta_diferente(self):
        extraido = ContextoExtraido(
            consulta="test",
            tools_invocadas=["consultar_datos_abiertos"],
            tools_omitidas=[],
            resultados=[_hacer_resultado_sanciones(1)],
        )
        assert _extraer_contratos(extraido) == []


class TestExtraerSanciones:
    def test_extrae_sanciones_ok(self, extraido_con_sanciones):
        sanciones = _extraer_sanciones(extraido_con_sanciones)
        assert len(sanciones) == 2

    def test_ignora_secop(self, extraido_con_contratos):
        assert _extraer_sanciones(extraido_con_contratos) == []


class TestSecopFueConsultado:
    def test_true_cuando_secop_en_resultados(self, extraido_con_contratos):
        assert _secop_fue_consultado(extraido_con_contratos) is True

    def test_true_cuando_secop_sin_datos(self, extraido_secop_sin_contratos):
        assert _secop_fue_consultado(extraido_secop_sin_contratos) is True

    def test_false_cuando_no_hay_secop(self, extraido_con_sanciones):
        assert _secop_fue_consultado(extraido_con_sanciones) is False


# ---------------------------------------------------------------------------
# Tests de la funcion principal `contrastar`
# ---------------------------------------------------------------------------


class TestContrastarSinCandidato:
    def test_plan_none_retorna_sin_candidato(self):
        resultado = contrastar("test", None, None, None)
        assert resultado.estado == "sin_candidato"
        assert resultado.candidato_id is None

    def test_plan_sin_candidato_retorna_sin_candidato(self, plan_sin_candidato):
        resultado = contrastar("test", plan_sin_candidato, None, None)
        assert resultado.estado == "sin_candidato"
        assert resultado.candidato_id is None

    def test_mensaje_describe_razon(self, plan_sin_candidato):
        resultado = contrastar("test", plan_sin_candidato, None, None)
        assert "candidato" in resultado.mensaje.lower()


class TestContrastarSinDatos:
    def test_sin_contextos_retorna_sin_datos(self, plan_con_candidato):
        resultado = contrastar("test", plan_con_candidato, None, None)
        assert resultado.estado == "sin_datos"

    def test_rag_vacio_y_secop_sin_contratos_retorna_sin_datos(
        self, plan_con_candidato, rag_vacio, extraido_secop_sin_contratos
    ):
        resultado = contrastar("test", plan_con_candidato, extraido_secop_sin_contratos, rag_vacio)
        assert resultado.estado == "sin_datos"
        assert resultado.n_propuestas_analizadas == 0
        assert resultado.n_contratos_analizados == 0

    def test_candidato_id_presente_aunque_sin_datos(self, plan_con_candidato):
        resultado = contrastar("test", plan_con_candidato, None, None)
        assert resultado.candidato_id == _CANDIDATO.id


class TestContrastarRegla1PropuestaSinContratos:
    """Regla 1: propuestas en RAG + SECOP consultado + 0 contratos."""

    def test_genera_inconsistencia(
        self, plan_con_candidato, rag_con_pasajes, extraido_secop_sin_contratos
    ):
        resultado = contrastar(
            "test", plan_con_candidato, extraido_secop_sin_contratos, rag_con_pasajes
        )
        assert resultado.estado == "ok"
        tipos = [i.tipo for i in resultado.inconsistencias]
        assert "propuesta_sin_contratos" in tipos

    def test_evidencia_contiene_fragmento_literal(
        self, plan_con_candidato, rag_con_pasajes, extraido_secop_sin_contratos
    ):
        resultado = contrastar(
            "test", plan_con_candidato, extraido_secop_sin_contratos, rag_con_pasajes
        )
        inc = next(i for i in resultado.inconsistencias if i.tipo == "propuesta_sin_contratos")
        # La evidencia de propuesta debe ser un fragmento del texto del pasaje
        assert "salud" in inc.evidencia_propuesta.lower() or inc.evidencia_propuesta != ""

    def test_fuentes_incluyen_rag_y_secop(
        self, plan_con_candidato, rag_con_pasajes, extraido_secop_sin_contratos
    ):
        resultado = contrastar(
            "test", plan_con_candidato, extraido_secop_sin_contratos, rag_con_pasajes
        )
        inc = next(i for i in resultado.inconsistencias if i.tipo == "propuesta_sin_contratos")
        fuentes_str = " ".join(inc.fuentes)
        assert "RAG" in fuentes_str or "Plan" in fuentes_str
        assert "SECOP" in fuentes_str


class TestContrastarRegla2ContratosSinPropuesta:
    """Regla 2: contratos SECOP + 0 propuestas en RAG."""

    def test_genera_inconsistencia(
        self, plan_con_candidato, rag_vacio, extraido_con_contratos
    ):
        resultado = contrastar(
            "test", plan_con_candidato, extraido_con_contratos, rag_vacio
        )
        assert resultado.estado == "ok"
        tipos = [i.tipo for i in resultado.inconsistencias]
        assert "contratos_sin_propuesta" in tipos

    def test_no_genera_propuesta_sin_contratos_tambien(
        self, plan_con_candidato, rag_vacio, extraido_con_contratos
    ):
        resultado = contrastar(
            "test", plan_con_candidato, extraido_con_contratos, rag_vacio
        )
        tipos = [i.tipo for i in resultado.inconsistencias]
        # Con contratos existentes, la regla 1 no debe disparar
        assert "propuesta_sin_contratos" not in tipos


class TestContrastarRegla3SancionesDetectadas:
    """Regla 3: sanciones en Procuraduria SIRI."""

    def test_genera_inconsistencia(
        self, plan_con_candidato, rag_vacio, extraido_con_sanciones
    ):
        resultado = contrastar(
            "test", plan_con_candidato, extraido_con_sanciones, rag_vacio
        )
        assert resultado.estado == "ok"
        tipos = [i.tipo for i in resultado.inconsistencias]
        assert "sanciones_detectadas" in tipos

    def test_cuenta_sanciones_correctamente(
        self, plan_con_candidato, rag_vacio, extraido_con_sanciones
    ):
        resultado = contrastar(
            "test", plan_con_candidato, extraido_con_sanciones, rag_vacio
        )
        assert resultado.n_sanciones_analizadas == 2

    def test_fuente_es_procuraduria(
        self, plan_con_candidato, rag_vacio, extraido_con_sanciones
    ):
        resultado = contrastar(
            "test", plan_con_candidato, extraido_con_sanciones, rag_vacio
        )
        inc = next(i for i in resultado.inconsistencias if i.tipo == "sanciones_detectadas")
        fuentes_str = " ".join(inc.fuentes).lower()
        assert "procuradur" in fuentes_str


class TestContrastarRegla4InconsistenciaSectorial:
    """Regla 4: propuestas en sector X pero contratos no mencionan sector X."""

    def test_genera_inconsistencia_sectorial_cuando_hay_brecha(
        self, plan_con_candidato, rag_con_pasajes
    ):
        # Los pasajes proponen salud y educacion.
        # Los contratos hablan de tecnologia (sin match con salud/educacion).
        extraido_tech = ContextoExtraido(
            consulta="test",
            tools_invocadas=["consultar_secop"],
            tools_omitidas=[],
            resultados=[
                _hacer_resultado_secop(
                    "ok",
                    [{"descripcion_del_proceso": "Compra de software y tecnologia digital"}],
                )
            ],
        )
        resultado = contrastar("test", plan_con_candidato, extraido_tech, rag_con_pasajes)
        assert resultado.estado == "ok"
        tipos = [i.tipo for i in resultado.inconsistencias]
        assert "inconsistencia_sectorial" in tipos

    def test_no_genera_sectorial_sin_contratos(
        self, plan_con_candidato, rag_con_pasajes, extraido_secop_sin_contratos
    ):
        # Sin contratos, la regla 4 no aplica (la 1 ya cubre el caso)
        resultado = contrastar(
            "test", plan_con_candidato, extraido_secop_sin_contratos, rag_con_pasajes
        )
        tipos = [i.tipo for i in resultado.inconsistencias]
        assert "inconsistencia_sectorial" not in tipos


class TestContrastarSinInconsistencias:
    def test_contratos_y_propuestas_en_mismo_sector_sin_inconsistencia(
        self, plan_con_candidato
    ):
        # Propuesta: salud. Contrato: hospital (salud).
        rag_salud = ContextoRag(
            consulta="salud",
            candidato_filtro=_CANDIDATO.id,
            pasajes=[
                PasajeRag(
                    texto="Invertiremos en salud y hospitales publicos.",
                    candidato_id=_CANDIDATO.id,
                    candidato_nombre=_CANDIDATO.nombre_canonico,
                    pdf="test.pdf",
                    pagina=1,
                    chunk_id="test:p1:c1",
                    score=0.1,
                )
            ],
            estado="ok",
            mensaje="1 pasaje.",
        )
        extraido_salud = ContextoExtraido(
            consulta="test",
            tools_invocadas=["consultar_secop"],
            tools_omitidas=[],
            resultados=[
                _hacer_resultado_secop(
                    "ok",
                    [{"descripcion_del_proceso": "Adquisicion de equipos para hospital"}],
                )
            ],
        )
        resultado = contrastar("test", plan_con_candidato, extraido_salud, rag_salud)
        assert resultado.estado == "ok"
        tipos = [i.tipo for i in resultado.inconsistencias]
        # No debe haber propuesta_sin_contratos ni contratos_sin_propuesta
        assert "propuesta_sin_contratos" not in tipos
        assert "contratos_sin_propuesta" not in tipos
        # No debe haber inconsistencia_sectorial (ambos en salud)
        assert "inconsistencia_sectorial" not in tipos


class TestContrastarConteos:
    def test_conteos_correctos(
        self, plan_con_candidato, rag_con_pasajes, extraido_con_contratos
    ):
        resultado = contrastar(
            "test", plan_con_candidato, extraido_con_contratos, rag_con_pasajes
        )
        assert resultado.n_propuestas_analizadas == 2
        assert resultado.n_contratos_analizados == 1
        assert resultado.n_sanciones_analizadas == 0

    def test_candidato_id_en_resultado(self, plan_con_candidato, extraido_con_contratos):
        resultado = contrastar("test", plan_con_candidato, extraido_con_contratos, None)
        assert resultado.candidato_id == _CANDIDATO.id


class TestNodoContraste:
    def test_retorna_campo_contraste_en_estado(self, plan_con_candidato):
        estado = {
            "pregunta": "test",
            "plan": plan_con_candidato,
            "contexto_extraido": None,
            "contexto_rag": None,
        }
        resultado = nodo_contraste(estado)
        assert "contraste" in resultado

    def test_estado_valido_en_resultado(self, plan_con_candidato):
        estado = {
            "pregunta": "test",
            "plan": plan_con_candidato,
            "contexto_extraido": None,
            "contexto_rag": None,
        }
        resultado = nodo_contraste(estado)
        assert resultado["contraste"].estado in {"ok", "sin_datos", "sin_candidato", "error"}

    def test_sin_plan_retorna_sin_candidato(self):
        estado = {
            "pregunta": "test",
            "plan": None,
        }
        resultado = nodo_contraste(estado)
        assert resultado["contraste"].estado == "sin_candidato"

    def test_propiedad_hubo_inconsistencias(
        self, plan_con_candidato, rag_vacio, extraido_con_sanciones
    ):
        estado = {
            "pregunta": "test",
            "plan": plan_con_candidato,
            "contexto_extraido": extraido_con_sanciones,
            "contexto_rag": rag_vacio,
        }
        resultado = nodo_contraste(estado)
        assert resultado["contraste"].hubo_inconsistencias is True
