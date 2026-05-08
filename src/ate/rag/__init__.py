"""Modulo RAG sobre planes de gobierno - Sprint 3.

Componentes:
    - `cliente.py`: wrapper sobre ChromaDB persistente con filtros por candidato.
    - `ingestor.py`: parseo PDFs (pypdf) -> chunks -> embeddings -> Chroma.

El agente que orquesta esto vive en `ate.agents.rag`. La tool registrada
es `buscar_plan_gobierno` en `ate.tools.rag_planes`.
"""

from ate.rag.cliente import ClienteRag, abrir_cliente
from ate.rag.ingestor import (
    chunkear_pdf,
    ingestar_candidato,
    ingestar_todos,
)

__all__ = [
    "ClienteRag",
    "abrir_cliente",
    "chunkear_pdf",
    "ingestar_candidato",
    "ingestar_todos",
]
