"""Ingestor de PDFs de planes de gobierno.

Pipeline:
    1. Leer cada PDF con pypdf.
    2. Para cada pagina, extraer texto y partirlo en chunks de tamano
       fijo con un solapamiento moderado (window-based).
    3. Tagear cada chunk con metadata: candidato_id, candidato_nombre,
       pdf, pagina, chunk_idx.
    4. Upsertar al cliente RAG. Idempotente: re-ingerir el mismo PDF
       sustituye los chunks anteriores del candidato.

Decisiones:
    - **Chunk size**: 800 chars, overlap 120. Equilibrio entre
      granularidad para queries cortas y contexto suficiente para
      preguntas amplias. Esto se puede afinar via `ATE_RAG_CHUNK_SIZE`
      / `ATE_RAG_CHUNK_OVERLAP`.
    - **Texto vacio**: paginas que no aportan texto (escaneos sin OCR)
      se ignoran silenciosamente; quedan en el log como warning.
    - **Idempotencia**: antes de cargar un candidato se borran sus
      chunks previos. Asi una segunda corrida no duplica.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from ate.candidatos.modelo import Candidato
from ate.candidatos.registro import CANDIDATOS_2026
from ate.rag.cliente import ClienteRag, abrir_cliente

logger = logging.getLogger(__name__)


_DEFAULT_CHUNK_SIZE = 800
_DEFAULT_CHUNK_OVERLAP = 120


@dataclass(frozen=True)
class Chunk:
    """Una unidad ingerible al vector store."""
    chunk_id: str
    texto: str
    candidato_id: str
    candidato_nombre: str
    pdf: str
    pagina: int


def _limpiar_texto(crudo: str) -> str:
    """Normaliza espacios, quita controles raros, preserva tildes."""
    if not crudo:
        return ""
    # Reemplazar saltos de linea sueltos en mitad de oraciones por espacio.
    # Mantener double-newlines como separadores de parrafo.
    crudo = re.sub(r"-\n", "", crudo)            # palabras cortadas
    crudo = re.sub(r"(?<!\n)\n(?!\n)", " ", crudo)  # newlines simples -> espacio
    crudo = re.sub(r"\s+", " ", crudo).strip()
    return crudo


def _ventanas(texto: str, tamano: int, overlap: int) -> Iterable[str]:
    """Itera sobre el texto en ventanas de `tamano` con solapamiento."""
    if not texto:
        return
    paso = max(1, tamano - overlap)
    n = len(texto)
    i = 0
    while i < n:
        yield texto[i: i + tamano]
        if i + tamano >= n:
            break
        i += paso


def chunkear_pdf(
    pdf_path: str | Path,
    *,
    candidato: Candidato,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = _DEFAULT_CHUNK_OVERLAP,
) -> List[Chunk]:
    """Lee un PDF y devuelve los chunks listos para upsertar.

    No toca ChromaDB: solo parsea + chunkea. El caller decide si los
    persiste o no.
    """
    import pypdf

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF no existe: {path}")

    reader = pypdf.PdfReader(str(path))
    chunks: List[Chunk] = []
    for nro_pagina, pagina in enumerate(reader.pages, start=1):
        try:
            texto = pagina.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 - pypdf puede explotar en PDFs raros
            logger.warning(
                "Fallo extraer pagina %d de %s: %s", nro_pagina, path.name, exc
            )
            continue
        texto = _limpiar_texto(texto)
        if not texto:
            continue
        for w_idx, ventana in enumerate(_ventanas(texto, chunk_size, chunk_overlap)):
            chunk_id = f"{candidato.id}:p{nro_pagina}:c{w_idx}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    texto=ventana,
                    candidato_id=candidato.id,
                    candidato_nombre=candidato.nombre_canonico,
                    pdf=str(path),
                    pagina=nro_pagina,
                )
            )
    return chunks


def ingestar_candidato(
    candidato: Candidato,
    *,
    cliente: Optional[ClienteRag] = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = _DEFAULT_CHUNK_OVERLAP,
    repo_root: str | Path = ".",
) -> int:
    """Ingesta el PDF de un candidato. Idempotente.

    Returns:
        cantidad de chunks insertados.
    """
    if not candidato.plan_pdf:
        logger.warning("Candidato %s sin plan_pdf — saltando", candidato.id)
        return 0
    pdf_path = Path(repo_root) / candidato.plan_pdf
    if not pdf_path.exists():
        logger.warning("PDF no encontrado para %s: %s", candidato.id, pdf_path)
        return 0

    cliente = cliente or abrir_cliente()
    # Idempotencia: borrar lo previo del mismo candidato.
    borrados = cliente.borrar_por_candidato(candidato.id)
    if borrados:
        logger.info("Borrados %d chunks previos de %s", borrados, candidato.id)

    chunks = chunkear_pdf(
        pdf_path,
        candidato=candidato,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    if not chunks:
        logger.warning("Sin chunks para %s (PDF sin texto extraible?)", candidato.id)
        return 0

    cliente.upsert_chunks(
        ids=[c.chunk_id for c in chunks],
        documentos=[c.texto for c in chunks],
        metadatas=[
            {
                "candidato_id": c.candidato_id,
                "candidato_nombre": c.candidato_nombre,
                "pdf": c.pdf,
                "pagina": c.pagina,
            }
            for c in chunks
        ],
    )
    logger.info("Ingestados %d chunks de %s", len(chunks), candidato.id)
    return len(chunks)


def ingestar_todos(
    *,
    cliente: Optional[ClienteRag] = None,
    repo_root: str | Path = ".",
) -> dict:
    """Ingesta todos los candidatos del registro.

    Returns:
        Dict {candidato_id: cantidad_de_chunks}.
    """
    cliente = cliente or abrir_cliente()
    chunk_size = int(os.getenv("ATE_RAG_CHUNK_SIZE", str(_DEFAULT_CHUNK_SIZE)))
    chunk_overlap = int(os.getenv("ATE_RAG_CHUNK_OVERLAP", str(_DEFAULT_CHUNK_OVERLAP)))
    resumen = {}
    for c in CANDIDATOS_2026:
        n = ingestar_candidato(
            c,
            cliente=cliente,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            repo_root=repo_root,
        )
        resumen[c.id] = n
    return resumen
