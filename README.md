# Agente de Gobierno
## Integrantes:
- Emanuel Zuluaga Restrepo
- Julian Cañas Saldarriaga
- Mateo Giraldo Soto
- Nicolas Paez Lancheros

# 🗳️ Agente de Transparencia Electoral (ATE) - Colombia 2026

El **ATE** es un agente de Inteligencia Artificial de vanguardia diseñado para auditar y centralizar información sobre los candidatos presidenciales en Colombia. Utiliza tecnologías de **Agentes Autónomos** y **RAG** para conectar planes de gobierno con datos reales de contratación y antecedentes, combatiendo la desinformación mediante la transparencia radical.

---

## 🎯 Objetivos del Proyecto
* **Neutralidad:** Proporcionar datos objetivos basados en evidencia, sin sesgos políticos.
* **Auditoría Ciudadana:** Facilitar el rastreo de contratos públicos (SECOP) y financiación de campañas.
* **Accesibilidad:** Traducir propuestas técnicas y densas de los planes de gobierno a lenguaje natural claro.

## 🛠️ Stack Tecnológico
* **Orquestador:** `LangGraph` (Para flujos cíclicos de razonamiento y corrección de errores).
* **IA Framework:** `LangChain`.
* **Modelos (LLM):** GPT-4o / Claude 3.5 Sonnet.
* **Base de Datos Vectorial:** `ChromaDB` o `Pinecone` (Para búsqueda semántica en propuestas).
* **Interfaz:** Streamlit (Prototipado rápido) o FastAPI + React.

---

## 📊 Fuentes de Datos y Conectividad
El agente consulta fuentes oficiales en tiempo real para evitar alucinaciones:

| Fuente | Tipo de Dato | Método de Acceso |
| :--- | :--- | :--- |
| **Portal Datos Abiertos** | Multas, sanciones y procesos. | API Socrata (`datos.gov.co`) |
| **SECOP I y II** | Historial de contratación pública. | API Socrata / SQL |
| **CNE (Cuentas Claras)** | Financiación de campañas. | Scraping / CSV |
| **Planes de Gobierno** | Propuestas oficiales de campaña. | Ingesta de PDFs (RAG) |
| **Search APIs** | Noticias y declaraciones recientes. | Tavily AI / Serper.dev |

---

## 🧠 Flujo de Trabajo (LangGraph)
El sistema opera como un grafo de decisión para asegurar la veracidad de la información:

1.  **Planificación:** El agente analiza la pregunta del usuario y decide qué herramientas (Tools) necesita.
2.  **Extracción:** Consulta las APIs de gobierno o la base de datos de propuestas.
3.  **Contraste:** Verifica si lo que el candidato propone coincide o contradice su historial de contratos o gestión previa.
4.  **Respuesta:** Genera una síntesis con **citación obligatoria** de enlaces oficiales.

---

## 7. Roadmap de Desarrollo

1. **Fase 1:** Configuración de entorno y obtención de credenciales (OpenAI, Socrata, Tavily).
2.   **Fase 2:** Ingesta de planes de gobierno en la base de datos vectorial.
3. **Fase 3:** Desarrollo de herramientas en Python para consulta dinámica de SECOP por nombre/cédula.
4. **Fase 4** Implementación del flujo lógico y ciclos de decisión en LangGraph.
5. **Fase 5:** Pruebas de mitigación de sesgos y validación de precisión de datos.

---

## 8. Consideraciones Éticas y Técnicas

**Transparencia de Fuente:** El agente no puede emitir juicios de valor ("es un mal candidato"), solo presentar datos objetivos ("el candidato tiene X contratos bajo investigación").

**Control de Alucinaciones:** Se implementará un paso de validación donde el LLM debe confirmar que el link de la fuente es funcional y oficial antes de entregar la respuesta al usuario.

**Declaración de Ausencia:** Si el dato no existe en las fuentes oficiales consultadas, el agente debe declarar explícitamente que no tiene la información en lugar de intentar deducirla.
