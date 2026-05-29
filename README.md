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

---

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

## 🚀 Ejecución y Uso

### Interfaz de Usuario (Streamlit)
Para iniciar la aplicación visual:
```bash
pip install streamlit
streamlit run app.py
```
La interfaz permite realizar consultas en lenguaje natural y visualizar la respuesta final con citaciones oficiales.

### CLI (Modo Resumen)
```bash
python -m ate -- la respuesta final se imprime en consola.
```

## 🧠 Arquitectura Final (Sprint 5)
El sistema opera como un grafo de decisión cíclico coordinado por **LangGraph**:

1. **Planificador:** Clasifica la intención y selecciona las herramientas.
2. **Extracción:** Consulta APIs oficiales (SECOP, Datos Abiertos, CNE).
3. **RAG:** Realiza búsqueda semántica en los planes de gobierno (PDFs).
4. **Contraste:** Cruza la evidencia de RAG vs Extracción para detectar inconsistencias.
5. **Validador:** Verifica que todas las URLs citadas sean dominios `.gov.co` oficiales.
6. **Generador:** Sintetiza una respuesta neutral, basada en evidencia y con citaciones obligatorias.

**Flujo:** `Usuario` $\rightarrow$ `Planificación` $\rightarrow$ `Extracción` $\rightarrow$ `RAG` $\rightarrow$ `Contraste` $\rightarrow$ `Validación` $\rightarrow$ `Generación` $\rightarrow$ `Respuesta Final`.

---

## 8. Consideraciones Éticas y Técnicas
**Transparencia de Fuente:** El agente no puede emitir juicios de valor ("es un mal candidato"), solo presentar datos objetivos ("el candidato tiene X contratos bajo investigación").

**Control de Alucinaciones:** Se implementará un paso de validación donde el LLM debe confirmar que el link de la fuente es funcional y oficial antes de entregar la respuesta al usuario.

**Declaración de Ausencia:** Si el dato no existe en las fuentes oficiales consultadas, el agente debe declarar explícitamente que no tiene la información en lugar de intentar deducirla.
---
### Para mas información ingrese acá:
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/NicolasPzL/Agente-de-Gobierno)
