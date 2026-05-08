"""Construccion del grafo LangGraph.

Topologia Sprint 3:

    __start__ -> planificador -> extraccion -> rag -> __end__

`extraccion` siempre corre (incluso para Intencion.INDEFINIDA produce un
ContextoExtraido vacio). `rag` decide internamente si invoca la base
vectorial — si la pregunta no amerita RAG (intencion != plan_gobierno
y sin candidato detectado), devuelve ContextoRag con estado=sin_datos
sin pegarle a Chroma. Esto mantiene el grafo lineal y predecible.

Topologia objetivo (sprints 4-5), declarada como hooks comentados:

    planificador -> extraccion ---> contraste (Sprint 4)
                  -> rag        ---^
    contraste     -> validador  (Sprint 4)
    validador     -> generador  (Sprint 5)
                   -> extraccion (ciclo si URL invalida)
    generador     -> END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from ate.agents.extraccion import nodo_extraccion
from ate.agents.planificador import nodo_planificador
from ate.agents.rag import nodo_rag
from ate.schemas.state import EstadoGrafo


def construir_grafo():
    """Compila el grafo del Sprint 3.

    Returns:
        Un grafo LangGraph compilado, listo para `.invoke({"pregunta": ...})`.
    """
    grafo = StateGraph(EstadoGrafo)
    grafo.add_node("planificador", nodo_planificador)
    grafo.add_node("extraccion", nodo_extraccion)
    grafo.add_node("rag", nodo_rag)

    grafo.set_entry_point("planificador")
    grafo.add_edge("planificador", "extraccion")
    grafo.add_edge("extraccion", "rag")
    grafo.add_edge("rag", END)

    # ------------------------------------------------------------------
    # Hooks para sprints futuros (NO descomentar hasta que existan los
    # modulos correspondientes en `ate.agents`):
    #
    # from ate.agents.contraste import nodo_contraste        # sprint 4
    # from ate.agents.validador import nodo_validador        # sprint 4
    # from ate.agents.generador import nodo_generador        # sprint 5
    #
    # grafo.add_node("contraste", nodo_contraste)
    # grafo.add_node("validador", nodo_validador)
    # grafo.add_node("generador", nodo_generador)
    #
    # grafo.add_edge("rag", "contraste")
    # grafo.add_edge("contraste", "validador")
    # grafo.add_edge("validador", "generador")
    # grafo.add_edge("generador", END)
    # ------------------------------------------------------------------

    return grafo.compile()
