"""Construccion del grafo LangGraph del Sprint 1.

Grafo actual:
    entrada -> planificador -> END

Grafo objetivo (sprints 2-5), dejado como hooks comentados mas abajo:
    planificador -> extraccion  (sprint 2)
                 -> rag          (sprint 3)
    extraccion   -> contraste    (sprint 4)
    rag          -> contraste
    contraste    -> validador    (sprint 4)
    validador    -> generador    (sprint 5)
    generador    -> END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from ate.agents.planificador import nodo_planificador
from ate.schemas.state import EstadoGrafo


def construir_grafo():
    """Compila el grafo del Sprint 1.

    Returns:
        Un grafo LangGraph compilado, listo para `.invoke({"pregunta": ...})`.
    """
    grafo = StateGraph(EstadoGrafo)
    grafo.add_node("planificador", nodo_planificador)

    grafo.set_entry_point("planificador")
    grafo.add_edge("planificador", END)

    # ------------------------------------------------------------------
    # Hooks para sprints futuros (NO descomentar hasta que existan los
    # modulos correspondientes en `ate.agents`):
    #
    # from ate.agents.extraccion import nodo_extraccion      # sprint 2
    # from ate.agents.rag import nodo_rag                    # sprint 3
    # from ate.agents.contraste import nodo_contraste        # sprint 4
    # from ate.agents.validador import nodo_validador        # sprint 4
    # from ate.agents.generador import nodo_generador        # sprint 5
    #
    # grafo.add_node("extraccion", nodo_extraccion)
    # grafo.add_node("rag", nodo_rag)
    # grafo.add_node("contraste", nodo_contraste)
    # grafo.add_node("validador", nodo_validador)
    # grafo.add_node("generador", nodo_generador)
    #
    # grafo.add_edge("planificador", "extraccion")
    # grafo.add_edge("planificador", "rag")
    # grafo.add_edge("extraccion", "contraste")
    # grafo.add_edge("rag", "contraste")
    # grafo.add_edge("contraste", "validador")
    # grafo.add_edge("validador", "generador")
    # grafo.add_edge("generador", END)
    # ------------------------------------------------------------------

    return grafo.compile()
