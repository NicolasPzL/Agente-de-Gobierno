"""Construccion del grafo LangGraph.

Topologia Sprint 5 (sistema multiagente completo):

    __start__ -> planificador -> (extraccion, rag) -> contraste -> validador
              -> generador -> __end__

El planificador abre en abanico hacia `extraccion` y `rag`, que corren en
paralelo (escriben claves distintas del estado, sin conflicto). `contraste`
hace fan-in: espera a que ambos terminen para cruzar propuestas (RAG) con
datos reales (extraccion). `validador` verifica que las URLs citadas sean de
fuentes oficiales colombianas. `generador` sintetiza la respuesta final con
citacion obligatoria.

Todos los nodos corren siempre — incluso para `Intencion.INDEFINIDA` la
extraccion produce un `ContextoExtraido` vacio, el RAG declara `sin_datos`,
el contraste `sin_candidato` y el validador `sin_fuentes`. Esto mantiene la
trazabilidad completa de la cadena de evidencia y evita ramas especiales.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from ate.agents.contraste import nodo_contraste
from ate.agents.extraccion import nodo_extraccion
from ate.agents.generador import nodo_generador
from ate.agents.planificador import nodo_planificador
from ate.agents.rag import nodo_rag
from ate.agents.validador import nodo_validador
from ate.schemas.state import EstadoGrafo


def construir_grafo():
    """Compila el grafo multiagente completo (Sprints 1-5).

    Topologia:
        __start__ -> planificador
        planificador -> extraccion   (paralelo)
        planificador -> rag          (paralelo)
        extraccion -> contraste      (fan-in)
        rag        -> contraste      (fan-in)
        contraste  -> validador
        validador  -> generador
        generador  -> END

    Returns:
        Un grafo LangGraph compilado, listo para `.invoke({"pregunta": ...})`.
    """
    grafo = StateGraph(EstadoGrafo)
    grafo.add_node("planificador", nodo_planificador)
    grafo.add_node("extraccion", nodo_extraccion)
    grafo.add_node("rag", nodo_rag)
    grafo.add_node("contraste", nodo_contraste)
    grafo.add_node("validador", nodo_validador)
    grafo.add_node("generador", nodo_generador)

    grafo.set_entry_point("planificador")

    # Fan-out: extraccion y rag se disparan en paralelo tras el planificador.
    grafo.add_edge("planificador", "extraccion")
    grafo.add_edge("planificador", "rag")

    # Fan-in: el contraste espera a que ambos terminen.
    grafo.add_edge("extraccion", "contraste")
    grafo.add_edge("rag", "contraste")

    grafo.add_edge("contraste", "validador")
    grafo.add_edge("validador", "generador")
    grafo.add_edge("generador", END)

    return grafo.compile()
