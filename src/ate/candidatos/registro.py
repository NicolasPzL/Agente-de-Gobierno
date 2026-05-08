"""Registro de los 13 candidatos presidenciales Colombia 2026.

Datos extraidos textualmente de los PDFs en `public/Candidatos/`. Los
alias estan elegidos para minimizar falsos positivos:
    - Apellidos compartidos (p.ej. "Lopez", "Uribe", "Valencia")
      requieren primer nombre o segundo apellido.
    - Solo se usan tokens >=4 caracteres como alias unicos para evitar
      colisiones con palabras comunes.
"""

from __future__ import annotations

from typing import List

from ate.candidatos.modelo import Candidato


_PATH_PDFS = "public/Candidatos"


CANDIDATOS_2026: List[Candidato] = [
    Candidato(
        id="ivan-cepeda",
        nombre_canonico="Ivan Cepeda Castro",
        nombre_corto="Ivan Cepeda",
        alias=["cepeda castro", "ivan cepeda", "cepeda"],
        partido="Pacto Historico",
        posicion_tarjeton=1,
        plan_pdf=f"{_PATH_PDFS}/candidatos_presidenciales_2026-Ivan Cepeda.pdf",
        cne_organizacion_id=28,
    ),
    Candidato(
        id="claudia-lopez",
        nombre_canonico="Claudia Nayibe Lopez Hernandez",
        nombre_corto="Claudia Lopez",
        alias=["claudia lopez", "claudia nayibe", "lopez hernandez"],
        partido="Movimiento Imparables",
        posicion_tarjeton=3,
        plan_pdf=f"{_PATH_PDFS}/candidatos_presidenciales_2026-Claudia Nayube Lopez.pdf",
    ),
    Candidato(
        id="raul-botero",
        nombre_canonico="Raul Santiago Botero Jaramillo",
        nombre_corto="Raul Botero",
        alias=["raul botero", "santiago botero", "botero jaramillo"],
        partido="Colombia Pa' Lante Unida",
        posicion_tarjeton=4,
        plan_pdf=f"{_PATH_PDFS}/candidatos_presidenciales_2026-Raul Santiago Botero.pdf",
    ),
    Candidato(
        id="abelardo-de-la-espriella",
        nombre_canonico="Abelardo Gabriel de la Espriella Otero",
        nombre_corto="Abelardo de la Espriella",
        alias=["de la espriella", "espriella otero", "abelardo de la espriella", "abelardo espriella"],
        partido="Defensores de la Patria - Salvacion Nacional",
        posicion_tarjeton=5,
        plan_pdf=f"{_PATH_PDFS}/candidatos_presidenciales_2026-Abelardo De Espriella.pdf",
    ),
    Candidato(
        id="oscar-lizcano",
        nombre_canonico="Oscar Mauricio Lizcano Arango",
        nombre_corto="Oscar Lizcano",
        alias=["oscar lizcano", "mauricio lizcano", "lizcano arango"],
        partido="Movimiento Colombianisimo - ASI",
        posicion_tarjeton=6,
        plan_pdf=f"{_PATH_PDFS}/candidatos_presidenciales_2026-Oscar Mauricio Lizcano.pdf",
    ),
    Candidato(
        id="miguel-uribe-londono",
        nombre_canonico="Miguel Uribe Londono",
        nombre_corto="Miguel Uribe Londono",
        # Cuidado: NO usar solo "uribe" para no colisionar con Alvaro Uribe Velez
        alias=["miguel uribe londono", "uribe londono"],
        partido="Partido Democrata Colombiano",
        posicion_tarjeton=7,
        plan_pdf=f"{_PATH_PDFS}/candidatos_presidenciales_2026-Miguel Uribe Londoño.pdf",
    ),
    Candidato(
        id="sondra-garvin",
        nombre_canonico="Sondra Macollins Garvin Pinto",
        nombre_corto="Sondra Garvin",
        alias=["sondra garvin", "sondra macollins", "garvin pinto"],
        partido="Movimiento Sondra Presidente",
        posicion_tarjeton=8,
        plan_pdf=f"{_PATH_PDFS}/candidatos_presidenciales_2026-Sondra Macollins Garvin.pdf",
    ),
    Candidato(
        id="roy-barreras",
        nombre_canonico="Roy Leonardo Barreras Montealegre",
        nombre_corto="Roy Barreras",
        alias=["roy barreras", "roy leonardo", "barreras montealegre"],
        partido="Agrupacion La Fuerza - Fuerza por la Paz",
        posicion_tarjeton=9,
        plan_pdf=f"{_PATH_PDFS}/candidatos_presidenciales_2026-Roy Leonardo Barreras.pdf",
    ),
    Candidato(
        id="carlos-caicedo",
        nombre_canonico="Carlos Eduardo Caicedo Omar",
        nombre_corto="Carlos Caicedo",
        alias=["carlos caicedo", "caicedo omar", "carlos eduardo caicedo"],
        partido="Fuerza Ciudadana",
        posicion_tarjeton=10,
        plan_pdf=f"{_PATH_PDFS}/candidatos_presidenciales_2026-Carlos Eduardo Caicedo.pdf",
    ),
    Candidato(
        id="gustavo-matamoros",
        nombre_canonico="Gustavo Matamoros Camacho",
        nombre_corto="Gustavo Matamoros",
        alias=["gustavo matamoros", "matamoros camacho"],
        partido="Partido Ecologista Colombiano",
        posicion_tarjeton=11,
        plan_pdf=f"{_PATH_PDFS}/candidatos_presidenciales_2026-Gustavo Matamoros Camacho.pdf",
    ),
    Candidato(
        id="paloma-valencia",
        nombre_canonico="Paloma Susana Valencia Laserna",
        nombre_corto="Paloma Valencia",
        # NO usar solo "valencia" (apellido demasiado comun)
        alias=["paloma valencia", "paloma susana", "valencia laserna"],
        partido="Centro Democratico",
        posicion_tarjeton=12,
        plan_pdf=f"{_PATH_PDFS}/candidatos_presidenciales_2026-Paloma Valencia.pdf",
    ),
    Candidato(
        id="sergio-fajardo",
        nombre_canonico="Sergio Fajardo Valderrama",
        nombre_corto="Sergio Fajardo",
        alias=["sergio fajardo", "fajardo valderrama", "fajardo"],
        partido="Dignidad y Compromiso",
        posicion_tarjeton=13,
        plan_pdf=f"{_PATH_PDFS}/candidatos_presidenciales_2026-Sergio Fajardo.pdf",
    ),
    Candidato(
        id="luis-gilberto-murillo",
        nombre_canonico="Luis Gilberto Murillo Urrutia",
        nombre_corto="Luis Gilberto Murillo",
        alias=["luis gilberto murillo", "gilberto murillo", "murillo urrutia"],
        partido="Colombia Renaciente",
        posicion_tarjeton=14,
        plan_pdf=f"{_PATH_PDFS}/candidatos_presidenciales_2026-Luis Gilberto Murillo.pdf",
    ),
]


def listar_candidatos() -> List[Candidato]:
    """Devuelve copia ordenada por posicion en tarjeton."""
    return sorted(
        CANDIDATOS_2026,
        key=lambda c: c.posicion_tarjeton if c.posicion_tarjeton is not None else 999,
    )


def por_id(candidato_id: str) -> Candidato | None:
    """Lookup por id (kebab-case)."""
    for c in CANDIDATOS_2026:
        if c.id == candidato_id:
            return c
    return None
