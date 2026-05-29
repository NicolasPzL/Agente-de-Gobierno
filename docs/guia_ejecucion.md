# Guia paso a paso - ejecutar y probar Sprints 1-5

Esta guia te lleva desde cero hasta correr los tests, la demo CLI
offline y la demo CLI con APIs reales (datos.gov.co / SECOP). Cubre
todo lo que ya esta implementado.

## 0. Requisitos previos

- **Python 3.11 o superior** (probado con 3.13). Verifica con:
  ```powershell
  python --version
  ```
- **Git** y una terminal: PowerShell o Git Bash en Windows; bash/zsh
  en Linux/macOS.

No necesitas API keys ni red para correr los tests: la suite fuerza
modo offline + clasificador determinista.

---

## 1. Situarte en el repo

```powershell
cd C:\girald0\estudio\pregrado\09\agentes\agenteGobierno
```

Verifica:

```powershell
ls
```

Deberias ver `pyproject.toml`, `src/`, `tests/`, `docs/`, `README.md`,
`CLAUDE.md`, `sprintRecomendaciones.md`, `.env.example`.

---

## 2. Crear un entorno virtual aislado

```powershell
python -m venv .venv
```

### 2.1 Activar el venv

**PowerShell** (Windows):

```powershell
.\.venv\Scripts\Activate.ps1
```

> Si PowerShell rechaza el script por politica de ejecucion, corre una
> sola vez:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

**Git Bash** (Windows):

```bash
source .venv/Scripts/activate
```

**Linux / macOS**:

```bash
source .venv/bin/activate
```

---

## 3. Instalar el paquete en modo editable

```powershell
pip install --upgrade pip
pip install -e ".[dev]"
```

Esto instala:

- `langgraph`, `langchain-core`, `pydantic`, `python-dotenv`, `requests`
  (runtime).
- `pytest` y `langchain-anthropic` (extras `dev`).
- El paquete `ate` editable.

Verifica:

```powershell
python -m ate --help
```

---

## 4. Correr la suite de tests

```powershell
pytest
```

Salida esperada (236 casos, ~3 segundos):

```
============================ 236 passed in 3.5s ============================
```

### 4.1 Ejecutar archivos / tests individuales

```powershell
pytest tests/test_planificador.py
pytest tests/test_extraccion.py
pytest tests/test_tools_apis.py -k secop
pytest -v                       # verbose
```

---

## 5. Demo CLI offline (sin red ni API keys)

Por defecto, si pones `ATE_OFFLINE=1` en `.env`, las tools no tocan la
red y devuelven `estado: "offline"` con la URL canonica conservada
para trazabilidad.

```powershell
$env:ATE_OFFLINE="1"
python -m ate --resumen "¿Que contratos tiene el candidato en SECOP?"
python -m ate --resumen "Donantes registrados en Cuentas Claras"
python -m ate --resumen "Sanciones disciplinarias"
python -m ate --resumen "¿Que propone en educacion?"
python -m ate --resumen "Hola, como estas"
```

Cada llamada imprime `plan` + `contexto_extraido` con los estados
correctos:

- `offline` para las tools que necesitarian red.
- `no_configurado` para CNE (sin dataset configurado) y RAG (Sprint 3).
- Sin tools y contexto vacio para `intencion=indefinida`.

---

## 6. Demo CLI online (datos.gov.co, SECOP)

```powershell
$env:ATE_OFFLINE="0"
python -m ate --resumen "Que contratos tiene Petro en SECOP"
```

Salida esperada: estado `ok` con ~50 contratos reales (25 SECOP I + 25
SECOP II) y URLs canonicas a `https://www.datos.gov.co/d/...`.

```powershell
python -m ate "Antecedentes disciplinarios de Hernandez"
```

(Sin `--resumen` se imprimen los registros crudos completos.)

> **Nota:** las APIs Socrata son publicas. Para subir el rate limit
> (de ~1 req/s a 1000 req/h), obtener un `SOCRATA_APP_TOKEN` gratis en
> https://www.datos.gov.co/profile/edit/developer_settings y ponerlo
> en `.env`.

---

## 7. Activar tools opcionales

### 7.1 CNE Cuentas Claras

Cuentas Claras no tiene API publica estable. Hay dos formas:

```ini
# .env - opcion A: dataset Socrata si existe para 2026
ATE_CNE_DATASET=<id_socrata>

# .env - opcion B: descargar y filtrar un CSV oficial
ATE_CNE_CSV_URL=https://www.cuentasclarasenelectoral.gov.co/path/al.csv
```

Sin nada de esto, la tool devuelve `estado: "no_configurado"` con un
mensaje claro (no inventa datos).

### 7.2 Buscador de noticias

```ini
# .env - opcion A: Tavily (recomendado, 1000 req/mes gratis)
ATE_NEWS_PROVIDER=tavily
TAVILY_API_KEY=tvly-...

# .env - opcion B: Serper (Google News)
ATE_NEWS_PROVIDER=serper
SERPER_API_KEY=...
```

Get keys:
- Tavily: https://app.tavily.com (gratis con email)
- Serper: https://serper.dev (gratis con email)

```powershell
python -m ate --resumen "Ultima entrevista de Petro"
```

---

## 8. Activar el camino LLM del planificador

Por defecto el planificador clasifica por palabras clave. Si quieres
probar con un LLM real (Claude via Anthropic):

```ini
# .env
ATE_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=tu_api_key_aqui
ATE_ANTHROPIC_MODEL=claude-sonnet-4-6
```

Tambien soporta Ollama local:

```ini
ATE_LLM_PROVIDER=ollama
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3-vl:8b
```

Si el LLM falla (red, key invalida, modelo no descargado), el
planificador **cae** al clasificador por palabras clave y lo deja
marcado en `razonamiento` con `(LLM no disponible: ...)`.

> **Importante:** los tests siempre fuerzan `ATE_LLM_PROVIDER=none` y
> `ATE_OFFLINE=1` aunque tengas `.env` configurado — ningun test toca
> red ni gasta tokens.

---

## 9. Desactivar el venv al terminar

```powershell
deactivate
```

---

## 10. Problemas comunes

| Sintoma | Causa probable | Solucion |
| :-- | :-- | :-- |
| `ModuleNotFoundError: ate` | Instalacion no editable, o venv no activado | `pip install -e ".[dev]"` con venv activo |
| `pytest` no se encuentra | Extras `dev` no instalados | `pip install -e ".[dev]"` |
| JSON con `?` o `�` en acentos (Windows) | Codepage de la consola | `chcp 65001` para UTF-8 |
| `ATE_LLM_PROVIDER invalido` | Valor no soportado en `.env` | `anthropic`, `openai`, `ollama` o `none` |
| `ANTHROPIC_API_KEY no configurada` | Provider=anthropic sin key | Rellenar key o cambiar provider |
| Tool devuelve `estado: "no_configurado"` | Falta env var de la fuente | Ver `.env.example` para la variable que pide |
| Tool devuelve `estado: "error_http"` | Dataset Socrata renombrado o caido | Ajustar `ATE_*_DATASET` o reintentar |
| Tool devuelve `estado: "offline"` con red disponible | `ATE_OFFLINE=1` activo | `$env:ATE_OFFLINE="0"` o ajustar `.env` |

---

## 11. Sprint 3 - RAG sobre planes de gobierno

Sprint 3 agrega busqueda semantica sobre los PDFs en
`public/Candidatos/`. Tienes que ingerirlos una sola vez:

```powershell
python scripts/ingestar_planes.py
```

Salida esperada (~50 segundos la primera vez por la descarga del modelo
ONNX, despues ~5s):

```
CANDIDATO                                CHUNKS
ivan-cepeda                              13
claudia-lopez                            7
abelardo-de-la-espriella                 13
paloma-valencia                          10
sergio-fajardo                           5
... (13 candidatos en total)
Total en coleccion: 78 chunks.
```

### 11.1 Demo del agente RAG con candidato detectado

```powershell
$env:ATE_OFFLINE="0"
python -m ate --resumen "¿Que propone Ivan Cepeda sobre derechos humanos?"
python -m ate --resumen "Plan de gobierno de Sergio Fajardo en educacion"
python -m ate --resumen "¿Que dice Paloma Valencia sobre seguridad?"
```

Cada llamada imprime `plan` (con `candidato.id` detectado),
`contexto_extraido` (tools de SECOP/datos.gov.co/CNE) y `contexto_rag`
con los pasajes recuperados (PDF, pagina, score).

### 11.2 Reingestar un solo candidato

```powershell
python scripts/ingestar_planes.py --solo paloma-valencia --reset
```

---

## 12. Sprint 4 - Contraste y validacion

Estos agentes corren automaticamente dentro del grafo. Para verlos en la
salida del CLI usa `--resumen`:

```powershell
$env:ATE_OFFLINE="0"
python -m ate --resumen "¿Que contratos tiene Ivan Cepeda y que propone en salud?"
```

La salida incluye `contraste` (inconsistencias propuesta vs. datos) y
`validacion` (dominios oficiales detectados).

---

## 13. Sprint 5 - Respuesta final + interfaz Streamlit

El grafo termina en el **agente generador**, que produce
`respuesta_final` con citacion obligatoria. El CLI la imprime arriba del
JSON tecnico:

```powershell
python -m ate "¿Que propone Sergio Fajardo en educacion?"
```

### 13.1 Interfaz web

```powershell
pip install -e ".[ui]"
streamlit run app.py
```

Abre http://localhost:8501. La app es un chat: escribe una pregunta y
veras la respuesta final + una cadena de evidencia auditable (plan,
contraste, RAG, extraccion, validacion) con enlaces a las fuentes.

### 13.2 Activar el LLM del generador

Igual que el planificador (seccion 8): configurar `ATE_LLM_PROVIDER`. Sin
LLM, el generador usa su modo determinista (sin alucinaciones). En modo
offline la app omite la auto-ingesta del RAG.
