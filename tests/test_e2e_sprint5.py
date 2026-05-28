import pytest
from ate.graph.builder import construir_grafo
from ate.config.settings import load_settings
from pydantic import ValidationError

def test_e2e_flow_full_cycle():
    """
    Verifica que el flujo completo (Plan -> Extraccion -> RAG -> Contraste -> Validador -> Generador)
    funcione correctamente y produzca una respuesta final citada.
    """
    # Forcamos modo offline para que el test sea determinista y rápido
    import os
    os.environ["ATE_OFFLINE"] = "1"
    os.environ["ATE_LLM_PROVIDER"] = "none" # Usamos el fallback determinista del generador

    grafo = construir_grafo()

    # Query que debería activar múltiples tools y el RAG
    pregunta = "¿Qué propone Iván Cepeda sobre derechos humanos y tiene contratos relacionados en SECOP?"

    resultado = grafo.invoke({"pregunta": pregunta})

    # 1. Verificar que llegamos al nodo final
    assert "respuesta_final" in resultado
    respuesta = resultado["respuesta_final"]
    assert isinstance(respuesta, str)
    assert len(respuesta) > 0

    # 2. Verificar que se incluyeron los componentes clave (en el fallback determinista)
    # El fallback concatena secciones como "--- Inconsistencias Detectadas ---" o "--- Datos Oficiales ---"
    assert "Análisis de Transparencia Electoral" in respuesta

    # 3. Verificar que la parte de diagnóstico LLM se expone correctamente
    assert "llm_info" in resultado
    assert resultado["llm_info"]["used_fallback"] is True

    # 4. Verificar que el estado interno es consistente
    assert "plan" in resultado
    assert "contexto_extraido" in resultado
    assert "contexto_rag" in resultado
    assert "contraste" in resultado
    assert "validacion" in resultado

def test_e2e_no_data_found():
    """
    Verifica que el sistema gestione correctamente la ausencia de datos
    sin inventar información (Control de Alucinaciones).
    """
    import os
    os.environ["ATE_OFFLINE"] = "1"
    os.environ["ATE_LLM_PROVIDER"] = "none"

    grafo = construir_grafo()

    # Query sobre un candidato inexistente o tema sin datos
    pregunta = "¿Qué propone el candidato Imaginario sobre la colonización de Marte?"

    resultado = grafo.invoke({"pregunta": pregunta})

    respuesta = resultado.get("respuesta_final", "")

    # El generador debe declarar explícitamente la ausencia de datos
    assert "no se ha encontrado evidencia oficial suficiente" in respuesta or "No se encontraron propuestas" in respuesta

def test_e2e_neutrality_check():
    """
    Verifica que el generador no emita juicios de valor.
    """
    import os
    os.environ["ATE_OFFLINE"] = "1"
    os.environ["ATE_LLM_PROVIDER"] = "none"

    grafo = construir_grafo()

    pregunta = "¿Es el candidato X un buen administrador?"
    resultado = grafo.invoke({"pregunta": pregunta})
    respuesta = resultado.get("respuesta_final", "").lower()

    # Palabras prohibidas en respuestas neutrales
    prohibidas = ["bueno", "malo", "excelente", "terrible", "sospechoso", "increible"]
    for p in prohibidas:
        assert p not in respuesta, f"La respuesta contiene un juicio de valor: {p}"
