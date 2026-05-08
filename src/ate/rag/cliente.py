"""Cliente de la base vectorial Chroma para planes de gobierno.

Wrapper minimo sobre `chromadb.PersistentClient` que:
    - Mantiene una sola coleccion (`planes_gobierno_2026`).
    - Usa la `DefaultEmbeddingFunction` de Chroma (`all-MiniLM-L6-v2`,
      ONNX, ~80MB, totalmente local). El modelo se descarga la primera
      vez que se abre el cliente; los siguientes runs son offline.
    - Soporta filtro por `candidato_id` para acotar la busqueda al PDF
      del candidato detectado por el planificador.

El cliente NO toca la red: ChromaDB persiste en disco
(`<rag_dir>/chroma`). Solo el primer run baja el modelo de embeddings
del cache de HuggingFace.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Nombre de la coleccion. Si cambia, hay que reingerir.
COLECCION = "planes_gobierno_2026"


@dataclass(frozen=True)
class Hit:
    """Un resultado de la busqueda vectorial, listo para `PasajeRag`."""

    chunk_id: str
    texto: str
    metadata: Dict[str, Any]
    distancia: float


class ClienteRag:
    """Wrapper sobre ChromaDB.

    Construir via `abrir_cliente(rag_dir)` para reusar el embedding
    function configurado.
    """

    def __init__(self, *, ruta_persistencia: Path, coleccion: str = COLECCION):
        self.ruta = ruta_persistencia
        self.nombre_coleccion = coleccion
        self._cliente = None
        self._coleccion = None
        self._embedder = None

    # --------------------------- inicializacion lazy ---------------------------

    def _abrir(self):
        if self._coleccion is not None:
            return
        # Importacion perezosa: si chromadb no esta instalado, el caller
        # decide como degradar gracefully (la tool retorna no_configurado).
        import chromadb
        from chromadb.utils import embedding_functions

        self.ruta.mkdir(parents=True, exist_ok=True)
        self._cliente = chromadb.PersistentClient(path=str(self.ruta))
        self._embedder = embedding_functions.DefaultEmbeddingFunction()
        self._coleccion = self._cliente.get_or_create_collection(
            name=self.nombre_coleccion,
            embedding_function=self._embedder,
            metadata={"hnsw:space": "cosine"},
        )

    # --------------------------- lectura ---------------------------

    def contar(self) -> int:
        """Cuantos chunks hay en la coleccion."""
        self._abrir()
        return self._coleccion.count()

    def buscar(
        self,
        consulta: str,
        *,
        k: int = 5,
        candidato_id: Optional[str] = None,
    ) -> List[Hit]:
        """Busqueda semantica top-k con filtro opcional por candidato.

        Args:
            consulta: texto en lenguaje natural.
            k: cuantos pasajes devolver.
            candidato_id: si se pasa, restringe a chunks de ese
                candidato (matching contra metadata `candidato_id`).
        """
        self._abrir()
        if not consulta or not consulta.strip():
            return []
        if self._coleccion.count() == 0:
            return []

        where: Optional[Dict[str, Any]] = None
        if candidato_id:
            where = {"candidato_id": candidato_id}

        resultado = self._coleccion.query(
            query_texts=[consulta],
            n_results=k,
            where=where,
        )
        # Chroma devuelve listas de listas (una por cada query_text).
        ids = resultado.get("ids", [[]])[0]
        documentos = resultado.get("documents", [[]])[0] or []
        metadatas = resultado.get("metadatas", [[]])[0] or []
        distancias = resultado.get("distances", [[]])[0] or []
        hits: List[Hit] = []
        for i, chunk_id in enumerate(ids):
            hits.append(
                Hit(
                    chunk_id=chunk_id,
                    texto=documentos[i] if i < len(documentos) else "",
                    metadata=metadatas[i] if i < len(metadatas) else {},
                    distancia=float(distancias[i]) if i < len(distancias) else 0.0,
                )
            )
        return hits

    # --------------------------- escritura (solo ingestor) ---------------------------

    def upsert_chunks(
        self,
        *,
        ids: List[str],
        documentos: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Inserta o actualiza chunks. Usado por el ingestor."""
        if not ids:
            return
        self._abrir()
        self._coleccion.upsert(
            ids=ids,
            documents=documentos,
            metadatas=metadatas,
        )

    def borrar_por_candidato(self, candidato_id: str) -> int:
        """Borra todos los chunks de un candidato. Util para reingestar."""
        self._abrir()
        existentes = self._coleccion.get(where={"candidato_id": candidato_id})
        ids = existentes.get("ids", []) or []
        if ids:
            self._coleccion.delete(ids=ids)
        return len(ids)


def abrir_cliente(rag_dir: str | Path | None = None) -> ClienteRag:
    """Abre (o reusa) un cliente RAG persistente.

    Args:
        rag_dir: directorio raiz para la persistencia. Si es None, lee
            `ATE_RAG_DIR` del entorno o usa `data/rag` por defecto.
    """
    if rag_dir is None:
        rag_dir = os.getenv("ATE_RAG_DIR", "data/rag")
    ruta = Path(rag_dir).resolve() / "chroma"
    return ClienteRag(ruta_persistencia=ruta)
