"""Registro de candidatos presidenciales Colombia 2026 + detector.

Sprint 2.5: este modulo se introduce para refinar las busquedas en las
APIs externas. Antes, cada tool recibia la pregunta cruda como `$q`
full-text. Ahora, el planificador identifica al candidato (si lo hay)
y el agente de extraccion reescribe la consulta por tool:

    SECOP / datos.gov.co -> nombre canonico ("Ivan Cepeda Castro")
    CNE                  -> partido / movimiento ("Pacto Historico")
    Buscador noticias    -> nombre + partido
    RAG planes gobierno  -> filtro por candidato_id en metadata

El registro se construye a mano desde los PDFs en `public/Candidatos/`
porque la fuente publica oficial (CNE 2026) no expone busqueda por
nombre. Cualquier candidato no listado pasa como `None` y las tools
caen al modo full-text genérico de Sprint 2.
"""

from ate.candidatos.modelo import Candidato
from ate.candidatos.registro import CANDIDATOS_2026, listar_candidatos
from ate.candidatos.extractor import detectar_candidato

__all__ = [
    "Candidato",
    "CANDIDATOS_2026",
    "listar_candidatos",
    "detectar_candidato",
]
