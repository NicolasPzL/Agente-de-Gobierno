import pytest

from ate.agents.generador import (
    _anexar_citas,
    _citas_oficiales,
    _extraer_texto_ollama,
    _formatear_contexto,
    _resumen_resultado,
    _sanitizar_texto,
    generar,
)
from ate.candidatos.registro import CANDIDATOS_2026
from ate.schemas.state import (
    ContextoExtraido,
    ContextoValidacion,
    Intencion,
    PlanEjecucion,
    ResultadoExtraccion,
    ValidacionFuente,
)


_CANDIDATO = CANDIDATOS_2026[0]  # Ivan Cepeda Castro


def test_sanitizar_texto_elimina_escape_y_normaliza():
    entrada = 'Respuesta con \\\"comillas\\\" y \\n saltos \\t y \\r retornos'
    esperado = 'Respuesta con "comillas" y saltos y retornos'
    assert _sanitizar_texto(entrada) == esperado


def test_extraer_texto_ollama_usa_response_y_thinking():
    assert _extraer_texto_ollama({"response": "hola"}) == "hola"
    assert _extraer_texto_ollama({"thinking": "pensando"}) == "pensando"


def test_extraer_texto_ollama_usa_output_con_texto():
    payload = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "texto completo"}
                ]
            }
        ]
    }
    assert _extraer_texto_ollama(payload) == "texto completo"


def test_extraer_texto_ollama_lanza_si_no_hay_texto():
    with pytest.raises(RuntimeError, match="no devolvió texto"):
        _extraer_texto_ollama({"output": []})


# ---------------------------------------------------------------------------
# Citacion obligatoria (Sprint 5)
# ---------------------------------------------------------------------------


def _estado_con_fuente_oficial() -> dict:
    url = "https://www.datos.gov.co/d/jbjy-vk9h"
    return {
        "pregunta": "¿Que contratos tiene Ivan Cepeda?",
        "plan": PlanEjecucion(
            intencion=Intencion.CONTRATACION,
            tools=["consultar_secop"],
            razonamiento="test",
            candidato=_CANDIDATO,
        ),
        "contexto_extraido": ContextoExtraido(
            consulta=_CANDIDATO.consulta_secop,
            tools_invocadas=["consultar_secop"],
            tools_omitidas=[],
            resultados=[
                ResultadoExtraccion(
                    fuente="SECOP",
                    tool="consultar_secop",
                    consulta=_CANDIDATO.consulta_secop,
                    estado="offline",
                    resultados=[],
                    total_resultados=0,
                    urls_oficiales=[url],
                    mensaje="offline",
                )
            ],
        ),
        "validacion": ContextoValidacion(
            fuentes_validadas=[
                ValidacionFuente(
                    url=url,
                    es_oficial=True,
                    accesible=None,
                    dominio_detectado="datos.gov.co",
                    observacion="oficial",
                )
            ],
            total_fuentes=1,
            fuentes_oficiales=1,
            fuentes_no_oficiales=0,
            estado="offline",
        ),
    }


class TestCitacionObligatoria:
    def test_citas_oficiales_prioriza_validacion(self):
        estado = _estado_con_fuente_oficial()
        citas = _citas_oficiales(estado)
        assert citas == ["https://www.datos.gov.co/d/jbjy-vk9h"]

    def test_citas_oficiales_excluye_no_oficiales(self):
        estado = _estado_con_fuente_oficial()
        estado["validacion"].fuentes_validadas.append(
            ValidacionFuente(
                url="https://semana.com/x",
                es_oficial=False,
                accesible=None,
                dominio_detectado="semana.com",
                observacion="no oficial",
            )
        )
        citas = _citas_oficiales(estado)
        assert "https://semana.com/x" not in citas
        assert "https://www.datos.gov.co/d/jbjy-vk9h" in citas

    def test_citas_oficiales_fallback_a_extraido_sin_validacion(self):
        estado = _estado_con_fuente_oficial()
        del estado["validacion"]
        citas = _citas_oficiales(estado)
        assert citas == ["https://www.datos.gov.co/d/jbjy-vk9h"]

    def test_anexar_citas_vacio_no_cambia_texto(self):
        assert _anexar_citas("Texto.", []) == "Texto."

    def test_anexar_citas_agrega_fuentes(self):
        salida = _anexar_citas("Texto", ["https://a.gov.co"])
        assert "Fuentes oficiales:" in salida
        assert "https://a.gov.co" in salida

    def test_generar_fallback_incluye_url_oficial(self):
        # provider=none (conftest) -> generar usa el fallback determinista.
        estado = _estado_con_fuente_oficial()
        respuesta = generar(estado["pregunta"], estado)
        assert "https://www.datos.gov.co/d/jbjy-vk9h" in respuesta
        assert "Fuentes oficiales:" in respuesta


# ---------------------------------------------------------------------------
# Fidelidad de la evidencia entregada al LLM (anti-alucinación)
# ---------------------------------------------------------------------------


class TestEvidenciaFiel:
    def test_resumen_declara_ausencia_si_no_ok(self):
        r = ResultadoExtraccion(
            fuente="CNE - Cuentas Claras 2026",
            tool="consultar_cne",
            consulta="Pacto Historico",
            estado="no_configurado",
            resultados=[],
            total_resultados=0,
            urls_oficiales=["https://www.cnecuentasclaras.gov.co/"],
            mensaje="No hay dataset configurado.",
        )
        out = _resumen_resultado(r)
        assert "no_configurado" in out
        assert "CNE" in out
        # No debe fabricar datos cuando no hay.
        assert "resultado(s)." not in out

    def test_resumen_muestra_datos_reales_si_ok(self):
        r = ResultadoExtraccion(
            fuente="SECOP I + SECOP II",
            tool="consultar_secop",
            consulta="Ivan Cepeda Castro",
            estado="ok",
            resultados=[{"objeto": "asesoria legislativa", "valor": "5000000"}],
            total_resultados=1,
            urls_oficiales=["https://www.datos.gov.co/d/jbjy-vk9h"],
            mensaje="1 contrato.",
        )
        out = _resumen_resultado(r)
        assert "objeto=asesoria legislativa" in out or "valor=5000000" in out

    def test_formatear_contexto_incluye_todas_las_fuentes_con_estado(self):
        estado = {
            "contexto_extraido": ContextoExtraido(
                consulta="financiacion",
                tools_invocadas=["consultar_cne", "consultar_secop"],
                tools_omitidas=[],
                resultados=[
                    ResultadoExtraccion(
                        fuente="CNE - Cuentas Claras 2026",
                        tool="consultar_cne",
                        consulta="Pacto Historico",
                        estado="sin_datos",
                        resultados=[],
                        total_resultados=0,
                        urls_oficiales=["https://www.cnecuentasclaras.gov.co/"],
                        mensaje="Sin registros de financiacion.",
                    ),
                    ResultadoExtraccion(
                        fuente="SECOP I + SECOP II",
                        tool="consultar_secop",
                        consulta="Ivan Cepeda Castro",
                        estado="ok",
                        resultados=[{"objeto": "consultoria"}],
                        total_resultados=1,
                        urls_oficiales=["https://www.datos.gov.co/d/jbjy-vk9h"],
                        mensaje="1 contrato.",
                    ),
                ],
            ),
        }
        secciones = _formatear_contexto(estado)
        # Ambas fuentes presentes, con su estado declarado (ausencia explícita).
        assert "CNE - Cuentas Claras 2026" in secciones["extraido"]
        assert "sin_datos" in secciones["extraido"]
        assert "SECOP" in secciones["extraido"]

    def test_formatear_contexto_contraste_neutral(self):
        from ate.schemas.state import ContextoContraste, InconsistenciaPropuesta

        estado = {
            "contraste": ContextoContraste(
                candidato_id="ivan-cepeda",
                inconsistencias=[
                    InconsistenciaPropuesta(
                        tipo="inconsistencia_sectorial",
                        descripcion="El plan menciona salud pero los contratos no registran ese sector.",
                        fuentes=["SECOP"],
                    )
                ],
                estado="ok",
                mensaje="1 observacion.",
            )
        }
        secciones = _formatear_contexto(estado)
        # Se etiqueta como heuristica automatica, no como prueba de irregularidad.
        assert "heur" in secciones["contraste"].lower()
