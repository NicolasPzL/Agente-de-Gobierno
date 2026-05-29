"""Servidor web del Agente de Transparencia Electoral (ATE) - Sprint 5.

Backend FastAPI que sirve el frontend (carpeta `web/`) y expone el grafo
multiagente con **streaming en vivo** del progreso por nodo via
Server-Sent Events (SSE). Asi el usuario ve "pensar" al agente paso a
paso (planificación → extracción → RAG → contraste → validación →
síntesis) en lugar de esperar a ciegas.

Ejecutar:
    pip install -e ".[web]"
    uvicorn serve:app --reload      # o:  python serve.py

Luego abrir http://localhost:8000
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Iterator

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import langchain

if not hasattr(langchain, "debug"):
    langchain.debug = False

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ate.candidatos.registro import CANDIDATOS_2026
from ate.config.settings import load_settings
from ate.graph.builder import construir_grafo

app = FastAPI(title="ATE — Transparencia Electoral 2026")

_WEB = _ROOT / "web"
app.mount("/static", StaticFiles(directory=str(_WEB)), name="static")


# Grafo compilado una sola vez (es costoso de construir).
_GRAFO = None


def grafo():
    global _GRAFO
    if _GRAFO is None:
        _GRAFO = construir_grafo()
    return _GRAFO


# Metadatos del pipeline para el timeline del frontend.
_PASOS = [
    {"node": "planificador", "label": "Planificación", "icon": "◷"},
    {"node": "extraccion", "label": "Extracción de fuentes", "icon": "⛏"},
    {"node": "rag", "label": "Planes de gobierno", "icon": "▤"},
    {"node": "contraste", "label": "Contraste", "icon": "⚖"},
    {"node": "validador", "label": "Validación de fuentes", "icon": "🛡"},
    {"node": "generador", "label": "Síntesis final", "icon": "✶"},
]
_LABELS = {p["node"]: p["label"] for p in _PASOS}


def _detalle(node: str, estado: dict) -> str:
    """Resumen humano de lo que produjo cada nodo (para el feedback en vivo)."""
    if node == "planificador":
        plan = estado.get("plan")
        if not plan:
            return ""
        cand = plan.candidato.nombre_corto if plan.candidato else "sin candidato"
        return f"Intención: {plan.intencion.value} · {cand}"
    if node == "extraccion":
        ext = estado.get("contexto_extraido")
        return f"{len(ext.resultados)} fuente(s) consultada(s)" if ext else ""
    if node == "rag":
        rag = estado.get("contexto_rag")
        return f"{len(rag.pasajes)} pasaje(s) · {rag.estado}" if rag else ""
    if node == "contraste":
        con = estado.get("contraste")
        return f"{len(con.inconsistencias)} inconsistencia(s) · {con.estado}" if con else ""
    if node == "validador":
        val = estado.get("validacion")
        if not val:
            return ""
        return f"{val.fuentes_oficiales} oficial(es) / {val.fuentes_no_oficiales} no oficial(es)"
    if node == "generador":
        return "Respuesta sintetizada con citación"
    return ""


def _serializar_evidencia(estado: dict) -> dict:
    """Convierte el estado del grafo en JSON para la cadena de evidencia."""
    def dump(obj):
        return obj.model_dump(mode="json") if obj is not None else None

    return {
        "plan": dump(estado.get("plan")),
        "extraccion": dump(estado.get("contexto_extraido")),
        "rag": dump(estado.get("contexto_rag")),
        "contraste": dump(estado.get("contraste")),
        "validacion": dump(estado.get("validacion")),
    }


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream(pregunta: str) -> Iterator[str]:
    inicio = time.time()
    estado: dict = {}
    try:
        yield _sse("start", {"pregunta": pregunta, "pasos": _PASOS})
        for chunk in grafo().stream({"pregunta": pregunta}, stream_mode="updates"):
            for node, delta in chunk.items():
                if isinstance(delta, dict):
                    estado.update(delta)
                yield _sse(
                    "step",
                    {
                        "node": node,
                        "label": _LABELS.get(node, node),
                        "detail": _detalle(node, estado),
                        "t": int((time.time() - inicio) * 1000),
                    },
                )
        yield _sse(
            "done",
            {
                "answer": estado.get("respuesta_final") or "",
                "evidence": _serializar_evidencia(estado),
                "llm_info": estado.get("llm_info") or {},
                "elapsed_ms": int((time.time() - inicio) * 1000),
            },
        )
    except Exception as exc:  # noqa: BLE001 - cualquier fallo se reporta al cliente
        yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})


@app.get("/")
def index():
    return FileResponse(str(_WEB / "index.html"))


@app.get("/api/config")
def config():
    cfg = load_settings()
    return JSONResponse(
        {
            "offline": cfg.ate_offline,
            "llm_provider": cfg.llm_provider,
            "llm_available": cfg.llm_available,
            "pasos": _PASOS,
            "candidatos": [
                {"nombre": c.nombre_corto, "partido": c.partido} for c in CANDIDATOS_2026
            ],
        }
    )


@app.get("/api/ask")
def ask(q: str = Query(..., min_length=1, max_length=500)):
    return StreamingResponse(
        _stream(q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
