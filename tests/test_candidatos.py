"""Tests del registro de candidatos 2026 + detector."""

from __future__ import annotations

import pytest

from ate.candidatos import CANDIDATOS_2026, Candidato, detectar_candidato
from ate.candidatos.registro import por_id


def test_hay_13_candidatos_inscritos():
    assert len(CANDIDATOS_2026) == 13


def test_ids_son_unicos_y_kebab_case():
    ids = [c.id for c in CANDIDATOS_2026]
    assert len(ids) == len(set(ids))
    for cid in ids:
        assert cid.islower()
        assert " " not in cid
        assert "_" not in cid


def test_cada_candidato_tiene_partido_y_pdf_path():
    for c in CANDIDATOS_2026:
        assert c.partido, f"{c.id}: sin partido"
        assert c.plan_pdf, f"{c.id}: sin plan_pdf"
        assert c.plan_pdf.endswith(".pdf")


def test_consultas_por_tool_estables():
    cep = por_id("ivan-cepeda")
    assert cep is not None
    assert cep.consulta_secop == "Ivan Cepeda Castro"
    assert cep.consulta_datos_oficiales == "Ivan Cepeda Castro"
    assert cep.consulta_cne == "Pacto Historico"
    assert cep.consulta_noticias == "Ivan Cepeda Pacto Historico"


@pytest.mark.parametrize(
    "pregunta, id_esperado",
    [
        ("¿Que contratos tiene Ivan Cepeda?", "ivan-cepeda"),
        ("Antecedentes de Sergio Fajardo", "sergio-fajardo"),
        ("Plan de gobierno de Claudia Lopez", "claudia-lopez"),
        ("¿Que propone Paloma Valencia?", "paloma-valencia"),
        ("Donantes de Roy Barreras", "roy-barreras"),
        ("Sancion contra Miguel Uribe Londono", "miguel-uribe-londono"),
        ("Carlos Caicedo y Fuerza Ciudadana", "carlos-caicedo"),
        ("propuestas de Murillo Urrutia", "luis-gilberto-murillo"),
        ("De la Espriella en su discurso", "abelardo-de-la-espriella"),
    ],
)
def test_detector_encuentra_candidato(pregunta, id_esperado):
    c = detectar_candidato(pregunta)
    assert c is not None
    assert c.id == id_esperado


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Que dijo el presidente?",
        "Hola como estas",
        "Petro en el Congreso",            # Petro no es candidato 2026
        "Donantes de campana",
        "¿Hay sanciones?",
    ],
)
def test_detector_devuelve_none_si_no_hay_candidato(pregunta):
    assert detectar_candidato(pregunta) is None


def test_detector_es_insensible_a_tildes_y_mayusculas():
    c = detectar_candidato("¿Cuál es el plan de IVÁN CEPEDA?")
    assert c is not None
    assert c.id == "ivan-cepeda"


def test_detector_prefiere_match_mas_especifico():
    """Si hay un alias mas largo que matchea, gana sobre uno mas corto."""
    c = detectar_candidato("Miguel Uribe Londono se pronuncio")
    assert c is not None
    assert c.id == "miguel-uribe-londono"


def test_detector_pregunta_vacia():
    assert detectar_candidato("") is None
    assert detectar_candidato("   ") is None
