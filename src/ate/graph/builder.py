"""Construccion del grafo LangGraph.

Topologia Sprint 4:

    __start__ -> planificador -> extraccion -> rag -> contraste -> validador -> __end__

`extraccion` siempre corre (incluso para Intencion.INDEFINIDA produce un
ContextoExtraido vacio). `rag` decide internamente si invoca la base
vectorial. `contraste` compara propuestas del plan con datos reales.
`validador` verifica que las URLs citadas sean de fuentes oficiales.

Topologia objetivo (sprint 5), declarada como hook comentado:

    validador -> generador (Sprint 5)
    generador -> END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from ate.agents.contraste import nodo_contraste
from ate.agents.extraccion import nodo_extraccion
from ate.agents.planificador import nodo_planificador
from ate.agents.rag import nodo_rag
from ate.agents.validador import nodo_validador
from ate.schemas.state import EstadoGrafo


def construir_grafo():
    """Compila el grafo del Sprint 4.

    Returns:
        Un grafo LangGraph compilado, listo para `.invoke({"pregunta": ...})`.
    """
    grafo = StateGraph(EstadoGrafo)
    grafo.add_node("planificador", nodo_planificador)
    grafo.add_node("extraccion", nodo_extraccion)
    grafo.add_node("rag", nodo_rag)
    grafo.add_node("contraste", nodo_contraste)
    grafo.add_node("validador", nodo_validador)

    grafo.set_entry_point("planificador")
    grafo.add_edge("planificador", "extraccion")
    grafo.add_edge("extraccion", "rag")
    grafo.add_edge("rag", "contraste")
    grafo.add_edge("contraste", "validador")
    grafo.add_edge("validador", END)

    # ------------------------------------------------------------------
    # Hook para sprint futuro (NO descomentar hasta que exista el modulo):
    #
    # from ate.agents.generador import nodo_generador        # sprint 5
    # grafo.add_node("generador", nodo_generador)
    # grafo.add_edge("validador", "generador")
    # grafo.add_edge("generador", END)
    # ------------------------------------------------------------------

    return grafo.compile()
