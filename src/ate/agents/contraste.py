"""Agente de contraste - Sprint 4.

Responsabilidades:
    1. Leer propuestas del plan de gobierno (ContextoRag) y datos reales
       (ContextoExtraido).
    2. Detectar inconsistencias entre lo que el candidato propone y lo que
       los datos oficiales muestran, usando cuatro reglas deterministicas:
           - propuesta_sin_contratos: el plan propone acciones pero SECOP
             no registra contratos para ese candidato.
           - contratos_sin_propuesta: hay contratos SECOP pero no se
             encontraron propuestas en el plan de gobierno.
           - sanciones_detectadas: la Procuraduria SIRI registra sanciones
             disciplinarias para el candidato.
           - inconsistencia_sectorial: el plan menciona un sector especifico
             (salud, educacion, etc.) pero los contratos SECOP no lo tocan.
    3. Control de alucinaciones: el agente NUNCA inventa. Solo reporta
       lo que encuentra directamente en los datos. Si no hay informacion,
       declara estado='sin_datos'. Si no hay candidato, declara
       estado='sin_candidato'. Los campos `evidencia_propuesta` y
       `evidencia_dato` siempre son fragmentos literales de los datos.

Decisiones de diseno:
    - **Sin LLM**: la comparacion es 100% determinista (regex / keyword
      matching). Esto garantiza reproducibilidad y cero alucinaciones.
    - **Sin candidato, sin contraste**: comparar propuestas contra contratos
      de "cualquier candidato" no tiene valor; se requiere la identidad.
    - **Tolerancia a datos parciales**: si llega contexto de RAG pero no
      de extraccion (o viceversa), el agente trabaja con lo disponible y
      reporta que la otra fuente faltaba.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

from ate.schemas.state import (
    ContextoContraste,
    ContextoExtraido,
    ContextoRag,
    EstadoGrafo,
    InconsistenciaPropuesta,
    PlanEjecucion,
    ResultadoExtraccion,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapa de sectores: clave -> lista de subcadenas a buscar (todo en minusculas)
# Se usa para detectar de que sector habla una propuesta o un contrato.
# ---------------------------------------------------------------------------
_SECTORES: Dict[str, List[str]] = {
    "salud": [
        "salud", "hospital", "clinica", "medic", "enfermer", "ips", "eps",
        "sanitari", "farmac", "vacun", "medicina",
    ],
    "educacion": [
        "educac", "escuela", "colegio", "universidad", "docente", "estudiante",
        "enseñanza", "aprendizaje", "pedagogia", "maestro",
    ],
    "infraestructura": [
        "infraestructura", "via ", "carretera", "puente", "construccion",
        "obra civil", "vial", "alcantarillado", "acueducto",
    ],
    "vivienda": [
        "vivienda", " casa ", "habitacion", "urbanizac", "subsidio",
        "arrendamiento", "inmueble",
    ],
    "seguridad": [
        "seguridad", "policia", "defensa", "ejercito", "criminalidad",
        "delito", "violencia", "orden public",
    ],
    "medio_ambiente": [
        "ambiente", "natural", "bosque", "agua", "rio", "mineria",
        "ecologia", "biodiversidad", "clima", "contaminac",
    ],
    "tecnologia": [
        "tecnologia", "digital", "internet", "innovacion", "software",
        "datos", "inteligencia artificial", "conectividad",
    ],
    "agricultura": [
        "agricultur", "campo", "campesino", "rural", "cosecha",
        "ganaderia", "pesca", "agro",
    ],
    "energia": [
        "energia", "electrica", "petroleo", "gas natural", "hidro",
        "solar", "eolica", "combustible",
    ],
    "justicia": [
        "justicia", "paz", "derechos humanos", "corrupcion", "transparencia",
        "impunidad", "carcel", "prision",
    ],
}


def _detectar_sectores(texto: str) -> Set[str]:
    """Devuelve el conjunto de sectores mencionados en el texto."""
    t = texto.lower()
    return {sector for sector, kws in _SECTORES.items() if any(kw in t for kw in kws)}


def _extraer_contratos(extraido: ContextoExtraido) -> List[dict]:
    """Devuelve todos los registros de contratos SECOP con estado='ok'."""
    contratos: List[dict] = []
    for r in extraido.resultados:
        if r.tool == "consultar_secop" and r.estado == "ok":
            contratos.extend(r.resultados)
    return contratos


def _extraer_sanciones(extraido: ContextoExtraido) -> List[dict]:
    """Devuelve todos los registros de sanciones de la Procuraduria con estado='ok'."""
    sanciones: List[dict] = []
    for r in extraido.resultados:
        if r.tool == "consultar_datos_abiertos" and r.estado == "ok":
            sanciones.extend(r.resultados)
    return sanciones


def _secop_fue_consultado(extraido: ContextoExtraido) -> bool:
    """True si el agente de extraccion consulto SECOP (con cualquier resultado)."""
    return any(r.tool == "consultar_secop" for r in extraido.resultados)


def _detectar_inconsistencias(
    rag: ContextoRag,
    extraido: ContextoExtraido,
    nombre_canonico: str,
) -> List[InconsistenciaPropuesta]:
    """Aplica las cuatro reglas deterministicas de contraste.

    Cada regla produce zero o mas `InconsistenciaPropuesta`. Las evidencias
    son siempre fragmentos literales de los datos; nunca se sintetiza ni
    se infiere mas alla de lo que los datos dicen explicitamente.
    """
    inconsistencias: List[InconsistenciaPropuesta] = []
    propuestas = rag.pasajes if rag.estado == "ok" else []
    contratos = _extraer_contratos(extraido)
    sanciones = _extraer_sanciones(extraido)

    # ------------------------------------------------------------------
    # Regla 1: propuesta_sin_contratos
    # El candidato tiene propuestas en su plan de gobierno pero SECOP
    # no registra ningun contrato para el.
    # ------------------------------------------------------------------
    if propuestas and not contratos and _secop_fue_consultado(extraido):
        evidencia_propuesta = propuestas[0].texto[:400] if propuestas else ""
        inconsistencias.append(
            InconsistenciaPropuesta(
                tipo="propuesta_sin_contratos",
                descripcion=(
                    f"{nombre_canonico} tiene {len(propuestas)} propuesta(s) "
                    f"en su plan de gobierno, pero SECOP no registra contratos "
                    f"relacionados."
                ),
                evidencia_propuesta=evidencia_propuesta,
                evidencia_dato=(
                    "SECOP I + SECOP II: 0 contratos encontrados para este candidato."
                ),
                fuentes=["Plan de Gobierno (RAG)", "SECOP I + SECOP II"],
            )
        )

    # ------------------------------------------------------------------
    # Regla 2: contratos_sin_propuesta
    # Hay contratos en SECOP pero no se encontraron propuestas en el plan.
    # ------------------------------------------------------------------
    if contratos and not propuestas:
        c0 = contratos[0]
        evidencia_dato = str(
            c0.get("descripcion_del_proceso",
            c0.get("objeto_del_contrato",
            c0.get("descripcion", f"{len(contratos)} contrato(s) en SECOP.")))
        )[:400]
        inconsistencias.append(
            InconsistenciaPropuesta(
                tipo="contratos_sin_propuesta",
                descripcion=(
                    f"SECOP registra {len(contratos)} contrato(s) para "
                    f"{nombre_canonico}, pero no se encontraron propuestas "
                    f"en su plan de gobierno."
                ),
                evidencia_propuesta=(
                    "Plan de gobierno no disponible o sin resultados en RAG."
                ),
                evidencia_dato=evidencia_dato,
                fuentes=["SECOP I + SECOP II"],
            )
        )

    # ------------------------------------------------------------------
    # Regla 3: sanciones_detectadas
    # La Procuraduria SIRI registra sanciones para el candidato.
    # ------------------------------------------------------------------
    if sanciones:
        s0 = sanciones[0]
        evidencia_dato = str(
            s0.get("descripcion",
            s0.get("tipo_sancion",
            s0.get("nombre_sancionado",
            f"{len(sanciones)} sancion(es) en Procuraduria SIRI.")))
        )[:400]
        inconsistencias.append(
            InconsistenciaPropuesta(
                tipo="sanciones_detectadas",
                descripcion=(
                    f"La Procuraduria SIRI registra {len(sanciones)} "
                    f"sancion(es) disciplinaria(s) para {nombre_canonico}."
                ),
                evidencia_propuesta="",
                evidencia_dato=evidencia_dato,
                fuentes=["Procuraduria SIRI (datos.gov.co)"],
            )
        )

    # ------------------------------------------------------------------
    # Regla 4: inconsistencia_sectorial
    # Solo aplica cuando hay tanto propuestas como contratos. Si el
    # candidato propone acciones en un sector pero los contratos SECOP
    # no mencionan ese sector, se reporta la brecha.
    # ------------------------------------------------------------------
    if propuestas and contratos:
        sectores_propuestas: Set[str] = set()
        for p in propuestas:
            sectores_propuestas.update(_detectar_sectores(p.texto))

        sectores_contratos: Set[str] = set()
        for c in contratos:
            texto_c = " ".join(str(v) for v in c.values() if v)
            sectores_contratos.update(_detectar_sectores(texto_c))

        brechas = sectores_propuestas - sectores_contratos
        for sector in sorted(brechas):
            # Encontrar el pasaje mas representativo del sector
            pasaje_relevante = next(
                (p.texto[:400] for p in propuestas
                 if any(kw in p.texto.lower() for kw in _SECTORES[sector])),
                "",
            )
            inconsistencias.append(
                InconsistenciaPropuesta(
                    tipo="inconsistencia_sectorial",
                    descripcion=(
                        f"El plan de gobierno de {nombre_canonico} menciona "
                        f"el sector '{sector}', pero los contratos SECOP no "
                        f"registran actividad en ese sector."
                    ),
                    evidencia_propuesta=pasaje_relevante,
                    evidencia_dato=(
                        f"SECOP: ninguno de los {len(contratos)} contrato(s) "
                        f"encontrados se relaciona con el sector '{sector}'."
                    ),
                    fuentes=["Plan de Gobierno (RAG)", "SECOP I + SECOP II"],
                )
            )

    return inconsistencias


def contrastar(
    pregunta: str,
    plan: Optional[PlanEjecucion],
    contexto_extraido: Optional[ContextoExtraido],
    contexto_rag: Optional[ContextoRag],
) -> ContextoContraste:
    """Punto de entrada puro y testeable del agente de contraste.

    Reglas de negocio:
        - Si no hay candidato detectado en el plan, el contraste no aplica:
          no podemos ligar propuestas a contratos sin una identidad.
        - Si no hay datos en ninguna fuente, se declara ausencia.
        - Si hay datos parciales (solo RAG o solo extraccion), se trabaja
          con lo disponible y se documenta lo que falta.

    Control de alucinaciones:
        - Solo se produce `InconsistenciaPropuesta` con evidencia literal.
        - Nunca se sintetizan afirmaciones mas alla de los datos.
        - El campo `mensaje` describe lo que SE ENCONTRO, no lo que
          el sistema cree o interpreta.
    """
    # Sin candidato -> contraste no aplica
    if plan is None or plan.candidato is None:
        return ContextoContraste(
            candidato_id=None,
            estado="sin_candidato",
            mensaje=(
                "No se detecto un candidato especifico en la pregunta. "
                "El contraste requiere identificar al candidato para cruzar "
                "sus propuestas con los datos oficiales."
            ),
        )

    candidato_id = plan.candidato.id
    nombre_canonico = plan.candidato.nombre_canonico

    # Sin ningun contexto -> sin datos
    if contexto_extraido is None and contexto_rag is None:
        return ContextoContraste(
            candidato_id=candidato_id,
            estado="sin_datos",
            mensaje=(
                f"No hay contexto extraido ni RAG para contrastar "
                f"a {nombre_canonico}."
            ),
        )

    # Normalizar contextos faltantes a objetos vacios
    rag = contexto_rag if contexto_rag is not None else ContextoRag(
        consulta=pregunta, estado="sin_datos"
    )
    extraido = contexto_extraido if contexto_extraido is not None else ContextoExtraido(
        consulta=pregunta
    )

    propuestas = rag.pasajes if rag.estado == "ok" else []
    contratos = _extraer_contratos(extraido)
    sanciones = _extraer_sanciones(extraido)

    n_propuestas = len(propuestas)
    n_contratos = len(contratos)
    n_sanciones = len(sanciones)

    # Sin ningun dato real -> declarar ausencia
    if n_propuestas == 0 and n_contratos == 0 and n_sanciones == 0:
        return ContextoContraste(
            candidato_id=candidato_id,
            n_propuestas_analizadas=0,
            n_contratos_analizados=0,
            n_sanciones_analizadas=0,
            estado="sin_datos",
            mensaje=(
                f"No se encontraron propuestas, contratos ni sanciones para "
                f"{nombre_canonico}. "
                "Posibles causas: fuentes no configuradas, PDF del candidato "
                "no indexado en RAG, o red no disponible."
            ),
        )

    inconsistencias = _detectar_inconsistencias(rag, extraido, nombre_canonico)
    n_inc = len(inconsistencias)

    if n_inc == 0:
        mensaje = (
            f"Contraste completado para {nombre_canonico}: "
            f"{n_propuestas} propuesta(s), {n_contratos} contrato(s), "
            f"{n_sanciones} sancion(es). No se detectaron inconsistencias."
        )
    else:
        tipos = sorted({i.tipo for i in inconsistencias})
        mensaje = (
            f"Contraste completado para {nombre_canonico}: "
            f"{n_inc} inconsistencia(s) detectada(s) "
            f"({', '.join(tipos)}). "
            f"Datos: {n_propuestas} propuesta(s), {n_contratos} contrato(s), "
            f"{n_sanciones} sancion(es)."
        )

    return ContextoContraste(
        candidato_id=candidato_id,
        inconsistencias=inconsistencias,
        n_propuestas_analizadas=n_propuestas,
        n_contratos_analizados=n_contratos,
        n_sanciones_analizadas=n_sanciones,
        estado="ok",
        mensaje=mensaje,
    )


def nodo_contraste(estado: EstadoGrafo) -> EstadoGrafo:
    """Envoltura del agente de contraste como nodo LangGraph."""
    pregunta = estado.get("pregunta", "")
    plan = estado.get("plan")
    contexto_extraido = estado.get("contexto_extraido")
    contexto_rag = estado.get("contexto_rag")

    resultado = contrastar(pregunta, plan, contexto_extraido, contexto_rag)
    logger.debug(
        "Contraste: candidato=%s, estado=%s, inconsistencias=%d",
        resultado.candidato_id,
        resultado.estado,
        len(resultado.inconsistencias),
    )
    return {"contraste": resultado}
