RECOMENDACIÓN TÉCNICA Y PLAN DE SPRINTS
Proyecto: Agente de Transparencia Electoral (ATE) - Colombia 2026

------------------------------------------------------------
1. VISIÓN DEL PROYECTO
------------------------------------------------------------

El Agente de Transparencia Electoral (ATE) es un sistema multiagente basado en inteligencia artificial cuyo propósito es auditar, contrastar y centralizar información sobre candidatos presidenciales en Colombia.

El sistema no solo responde preguntas, sino que:
- consulta fuentes oficiales,
- cruza información,
- valida evidencia,
- y genera respuestas con citación verificable.

El valor diferencial es la "transparencia radical basada en evidencia".

------------------------------------------------------------
2. ENFOQUE DE AGENTES DE IA
------------------------------------------------------------

El sistema está compuesto por agentes especializados:

- Agente Planificador: decide qué hacer
- Agente de Extracción: consulta fuentes externas
- Agente RAG: consulta planes de gobierno
- Agente de Contraste: cruza información
- Agente Validador: evita alucinaciones
- Agente Generador: construye respuesta final

Todos los agentes trabajan orquestados mediante LangGraph.

------------------------------------------------------------
3. TECNOLOGÍAS RECOMENDADAS
------------------------------------------------------------

Lenguaje:
- Python

Framework de agentes:
- LangGraph (orquestador principal)
- LangChain (tools + RAG)

Modelos:
- GPT-4o o Claude 3.5 (principal)
- Ollama (opcional para pruebas locales)

RAG:
- ChromaDB o Pinecone

APIs:
- datos.gov.co (Socrata)
- SECOP I y II
- CNE (scraping o CSV)
- Tavily / Serper (búsqueda)

Backend:
- FastAPI

Frontend:
- Streamlit (prototipo)
- React (opcional avanzado)

Infraestructura:
- Docker

Pruebas:
- Pytest

------------------------------------------------------------
4. PLAN DE SPRINTS (ENFOQUE MULTIAGENTE)
------------------------------------------------------------

------------------------------------------------------------
SPRINT 1 — Arquitectura de Agentes + Agente Planificador
------------------------------------------------------------

Objetivo:
Definir arquitectura multiagente e implementar el agente planificador.

Historias de usuario:
- Como usuario, quiero hacer preguntas sobre candidatos.
- Como sistema, quiero decidir qué fuentes consultar.

Tareas:
- Diseñar arquitectura en LangGraph
- Definir agentes y roles
- Implementar agente planificador
- Detectar intención de consulta
- Definir tools base
- Configurar entorno (LLM, API keys)
- Estructurar repositorio

Entregables:
- Grafo base en LangGraph
- Agente planificador funcional
- Flujo inicial de decisión

Criterios de aceptación:
- El agente identifica la intención
- Decide qué tools usar
- Arquitectura documentada

------------------------------------------------------------
SPRINT 2 — Agentes de Extracción (APIs reales)
------------------------------------------------------------

Objetivo:
Implementar agentes que consulten fuentes oficiales.

Historias de usuario:
- Como usuario, quiero consultar antecedentes de candidatos.
- Como sistema, quiero obtener datos desde APIs oficiales.

Tareas:
- Crear tools:
  - consulta datos.gov.co
  - consulta SECOP
  - consulta CNE
- Implementar agente de extracción
- Normalizar respuestas de APIs
- Manejar errores de consulta
- Integrar tools en LangChain

Entregables:
- Tools funcionales
- Agente de extracción conectado a APIs

Criterios de aceptación:
- El sistema consulta datos reales
- Devuelve información estructurada
- Maneja errores correctamente

------------------------------------------------------------
SPRINT 3 — RAG sobre Planes de Gobierno
------------------------------------------------------------

Objetivo:
Implementar agente de consulta semántica sobre propuestas.

Historias de usuario:
- Como usuario, quiero entender propuestas de candidatos.
- Como sistema, quiero buscar información en documentos.

Tareas:
- Ingestar PDFs de planes de gobierno
- Crear embeddings
- Indexar en ChromaDB/Pinecone
- Implementar agente RAG
- Diseñar prompts de búsqueda
- Integrar RAG con LangGraph

Entregables:
- Base vectorial funcional
- Agente RAG funcionando

Criterios de aceptación:
- El sistema responde usando documentos
- Encuentra información relevante
- Usa búsqueda semántica

------------------------------------------------------------
SPRINT 4 — Agente de Contraste y Validación
------------------------------------------------------------

Objetivo:
Cruzar información y validar veracidad.

Historias de usuario:
- Como usuario, quiero saber si un candidato es coherente.
- Como sistema, quiero contrastar propuestas con hechos.

Tareas:
- Implementar agente de contraste
- Diseñar lógica de comparación:
  - propuestas vs contratos
- Implementar agente validador
- Validar enlaces y fuentes
- Implementar control de alucinaciones
- Manejar ausencia de datos

Entregables:
- Agente de contraste funcional
- Sistema de validación de fuentes

Criterios de aceptación:
- El sistema cruza información
- Detecta inconsistencias
- No inventa datos
- Declara ausencia de información

------------------------------------------------------------
SPRINT 5 — Agente Generador + Interfaz + Producto Final
------------------------------------------------------------

Objetivo:
Construir la respuesta final y entregar el sistema completo.

Historias de usuario:
- Como usuario, quiero respuestas claras y verificables.
- Como evaluador, quiero un sistema completo y funcional.

Tareas:
- Implementar agente generador de respuestas
- Incluir citación obligatoria
- Mejorar prompts de salida
- Crear interfaz (Streamlit)
- Integrar flujo completo
- Realizar pruebas end-to-end
- Documentar sistema
- Preparar demo

Entregables:
- Sistema multiagente completo
- Interfaz funcional
- Respuestas con fuentes citadas
- Documentación

Criterios de aceptación:
- Respuestas claras y verificables
- Cita fuentes oficiales
- Flujo completo funcional
- No hay alucinaciones


------------------------------------------------------------
5. VALOR DIFERENCIAL
------------------------------------------------------------

Este sistema no solo responde preguntas, sino que:

- consulta fuentes oficiales
- cruza información
- valida evidencia
- cita fuentes verificables
- combate la desinformación

Esto lo convierte en un sistema de auditoría ciudadana basado en IA.

------------------------------------------------------------
6. RECOMENDACIONES CLAVE
------------------------------------------------------------

- Siempre citar fuentes oficiales
- Prohibir opiniones del modelo
- Validar enlaces antes de responder
- Declarar ausencia de datos
- Separar claramente los agentes
- No mezclar responsabilidades
- Mantener trazabilidad de cada respuesta


PD: le tengo mucha fé a este proyecto...