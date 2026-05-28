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
from ate.agents.generador import nodo_generador
from ate.schemas.state import EstadoGrafo


def ruta_despues_de_planificar(estado: EstadoGrafo) -> list[str]:
    """Decide si saltar directamente al generador o realizar auditoria completa.

    Fast-path: si no hay tools requeridas y no se detecto candidato,
    se asume que es una consulta simple (ej. saludo) y se va al generador.
    """
    plan = estado.get("plan")
    if plan and not plan.tools and plan.candidato is None:
        return ["generador"]
    return ["extraccion", "rag"]


def construir_grafo():
    """Compila el grafo del Sprint 4 con ejecución paralela de extracción y RAG.

    Topología Optimizada con Fast-Path:
        __start__ -> planificador
        planificador -> (extraccion, rag)  [si requiere auditoria]
        planificador -> generador         [si es consulta simple]
        extraccion -> contraste
        rag -> contraste
        contraste -> validador
        validador -> generador
        generador -> END

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

    # Enrutamiento condicional desde el planificador
    # Al retornar una lista, LangGraph dispara los nodos en paralelo.
    grafo.add_conditional_edges(
        "planificador",
        ruta_despues_de_planificar,
    )

    # Sincronización: el contraste espera que ambos terminen
    grafo.add_edge("extraccion", "contraste")
    grafo.add_edge("rag", "contraste")

    grafo.add_edge("contraste", "validador")
    grafo.add_edge("validador", "generador")
    grafo.add_edge("generador", END)

    return grafo.compile()
