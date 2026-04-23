# Guia paso a paso - ejecutar y probar el Sprint 1

Esta guia te lleva desde cero hasta ejecutar los tests y la demo del
planificador. Solo cubre lo que ya esta implementado en Sprint 1.

## 0. Requisitos previos

- **Python 3.11 o superior** (probado con 3.13). Verifica con:
  ```powershell
  python --version
  ```
- **Git** (para clonar si aun no lo hiciste) y una terminal:
  **PowerShell** o **Git Bash** en Windows; **bash/zsh** en Linux/macOS.

No necesitas API keys ni conexion a internet para correr los tests ni
la demo: el camino por defecto del planificador es determinista.

---

## 1. Situarte en el repo

```powershell
cd C:\girald0\estudio\pregrado\09\agentes\agenteGobierno
```

Verifica que estas en la carpeta correcta:

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

Esto crea la carpeta `.venv/` (ya esta en `.gitignore`).

### 2.1 Activar el venv

**PowerShell** (Windows):

```powershell
.\.venv\Scripts\Activate.ps1
```

> Si PowerShell rechaza el script por politica de ejecucion, corre una
> sola vez (como tu usuario):
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

El prompt deberia quedar con `(.venv)` al principio.

---

## 3. Instalar el paquete en modo editable con dependencias de desarrollo

```powershell
pip install --upgrade pip
pip install -e ".[dev]"
```

Esto instala:

- `langgraph`, `langchain-core`, `pydantic`, `python-dotenv` (runtime).
- `pytest` y `langchain-anthropic` (extras `dev`).
- El paquete `ate` en modo editable (puedes modificar `src/ate/` sin
  reinstalar).

Al terminar, verifica que el comando esta disponible:

```powershell
python -m ate --help
```

---

## 4. Correr la suite de tests

```powershell
pytest
```

Salida esperada (41 casos, en menos de 1 segundo):

```
============================= test session starts =============================
collected 41 items

tests\test_graph.py .......                                              [ 17%]
tests\test_planificador.py ....................                          [ 65%]
tests\test_tools.py ..............                                       [100%]

============================= 41 passed in 0.6s ==============================
```

### 4.1 Ejecutar un archivo o test individual

```powershell
pytest tests/test_planificador.py
pytest tests/test_graph.py::test_grafo_produce_plan_para_contratacion
pytest -k secop                 # solo tests que contengan "secop"
pytest -v                       # verbose: imprime el nombre de cada test
```

---

## 5. Probar la demo CLI

El entrypoint recibe una pregunta entre comillas y emite el plan
(intencion + tools + razonamiento) en JSON.

### 5.1 Casos por categoria de intencion

```powershell
python -m ate "¿Que contratos tiene el candidato X en SECOP?"
python -m ate "Donantes y aportes en Cuentas Claras"
python -m ate "Sanciones disciplinarias del candidato"
python -m ate "¿Que propone en educacion?"
python -m ate "Ultima entrevista del candidato"
python -m ate "Hola, como estas?"
```

Cada una deberia devolver una `intencion` distinta
(`contratacion`, `financiacion`, `datos_oficiales`, `plan_gobierno`,
`noticias`, `indefinida`) y la tool correspondiente (o lista vacia
para `indefinida`).

Ejemplo de salida:

```json
{
  "pregunta": "¿Que contratos tiene el candidato X en SECOP?",
  "plan": {
    "intencion": "contratacion",
    "tools": ["consultar_secop"],
    "razonamiento": "Palabra clave detectada: 'secop'."
  }
}
```

### 5.2 Ver logs internos

```powershell
python -m ate -v "Sanciones del candidato"
```

Imprime ademas los logs `DEBUG` del planificador y del grafo.

---

## 6. (Opcional) Activar el camino LLM estructurado

Por defecto el planificador clasifica por palabras clave. Si quieres
probar el clasificador con un LLM real (Claude via Anthropic):

### 6.1 Copiar la plantilla de entorno

```powershell
# PowerShell
Copy-Item .env.example .env
```

```bash
# Git Bash / Linux / macOS
cp .env.example .env
```

### 6.2 Editar `.env`

Abre `.env` en un editor y ajusta:

```
ATE_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=tu_api_key_aqui
# ATE_ANTHROPIC_MODEL=claude-sonnet-4-6   # opcional
```

### 6.3 Volver a ejecutar la demo

```powershell
python -m ate "¿Como financia su campana?"
```

El campo `razonamiento` ahora vendra del LLM. Si el LLM falla (red caida,
key invalida), el planificador **cae** al clasificador por palabras
clave y lo deja marcado en `razonamiento` con un aviso del tipo
`(LLM no disponible: ...)`.

> **Nota:** los tests (`pytest`) **siempre** fuerzan el camino
> determinista aunque tengas `.env` configurado — ningun test toca red.

---

## 7. Desactivar el venv al terminar

```powershell
deactivate
```

---

## 8. Problemas comunes

| Sintoma | Causa probable | Solucion |
| :-- | :-- | :-- |
| `ModuleNotFoundError: ate` | Instalacion no editable, o venv no activado | Activa `.venv` y corre `pip install -e ".[dev]"` de nuevo |
| `pytest` no se encuentra | Extras `dev` no instalados | `pip install -e ".[dev]"` |
| JSON de la CLI muestra `?` o `�` en acentos | Codepage de la consola (Windows) | Es solo visual; los datos son correctos. Puedes ejecutar `chcp 65001` en PowerShell para UTF-8 |
| `ATE_LLM_PROVIDER invalido` | Valor no soportado en `.env` | Usa uno de: `anthropic`, `openai`, `ollama`, `none` |
| `ANTHROPIC_API_KEY no configurada` | `.env` sin key pero provider=anthropic | Rellena la key o pon `ATE_LLM_PROVIDER=none` |

---

## 9. Que viene despues

Sprints 2–5 (ver `sprintRecomendaciones.md` y `docs/arquitectura_sprint1.md`):

- **Sprint 2:** reemplazar stubs de `datos_abiertos`, `secop`, `cne`,
  `buscar_noticias` por clientes reales.
- **Sprint 3:** ingesta de PDFs + base vectorial + agente RAG.
- **Sprint 4:** agentes de contraste y validador.
- **Sprint 5:** agente generador + interfaz + demo end-to-end.
