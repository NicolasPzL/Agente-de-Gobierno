"""Detector de candidato en texto libre.

Sprint 2.5: clasificador deterministico que busca alias y nombres
canonicos en la pregunta del usuario. No usa LLM; corre en
microsegundos y respeta la regla "ningun camino default toca red".

Estrategia:
    1. Normalizar pregunta (lowercase + sin tildes).
    2. Iterar candidatos por **especificidad descendente**: alias mas
       largos primero, para que "miguel uribe londono" gane sobre
       "miguel uribe" y este sobre "uribe".
    3. Retornar el primer match. La eleccion es estable porque cada
       alias es unico en el registro.

Si la pregunta menciona varios candidatos (caso comparativo, raro
para Sprint 2/3), se devuelve el primero detectado y se anota en el
razonamiento. Sprint 4 podra extender a comparaciones.
"""

from __future__ import annotations

import unicodedata
from typing import List, Optional

from ate.candidatos.modelo import Candidato
from ate.candidatos.registro import CANDIDATOS_2026


def _normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _patrones_de_busqueda(c: Candidato) -> List[str]:
    """Lista de patrones a buscar para un candidato, mas especifico primero."""
    patrones = [_normalizar(p) for p in c.alias]
    # Tambien permitir el nombre canonico completo y el corto.
    patrones.append(_normalizar(c.nombre_canonico))
    patrones.append(_normalizar(c.nombre_corto))
    # Deduplicar manteniendo orden (mas especifico primero por longitud).
    patrones = sorted(set(patrones), key=len, reverse=True)
    return [p for p in patrones if p]


def detectar_candidato(texto: str) -> Optional[Candidato]:
    """Devuelve el candidato mencionado en `texto`, o None.

    Args:
        texto: pregunta del usuario u oraci�n libre.

    Returns:
        El primer `Candidato` con un alias o nombre que aparezca como
        substring en `texto` (ya normalizado). None si nada matchea.
    """
    if not texto or not texto.strip():
        return None
    q = _normalizar(texto)

    # Construir lista plana (patron, candidato) ordenada por longitud
    # descendente para que el match mas largo gane.
    candidatos: List[tuple[str, Candidato]] = []
    for c in CANDIDATOS_2026:
        for patron in _patrones_de_busqueda(c):
            candidatos.append((patron, c))
    candidatos.sort(key=lambda pc: len(pc[0]), reverse=True)

    for patron, candidato in candidatos:
        if patron in q:
            return candidato
    return None
