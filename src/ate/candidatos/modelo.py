"""Modelo Pydantic para un candidato presidencial 2026."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Candidato(BaseModel):
    """Snapshot inmutable de un candidato registrado para 2026.

    Atributos:
        id: identificador estable (slug en kebab-case). Sirve como
            metadata key en ChromaDB y referencia cruzada en la traza.
        nombre_canonico: como se debe usar en SECOP / datos.gov.co.
        nombre_corto: forma comun para mensajes legibles.
        alias: substrings que disparan deteccion (case-insensitive,
            sin tildes). Deben ser **especificas** — evitar palabras
            comunes que generen falsos positivos.
        partido: nombre del partido o movimiento. Se usa para el match
            de organizacion en CNE Cuentas Claras.
        posicion_tarjeton: numero asignado por el CNE.
        plan_pdf: path relativo al repo del PDF con el plan de gobierno.
            Lo consume el ingestor RAG (Sprint 3).
        cne_organizacion_id: ID de organizacion en la API publica del
            CNE (cuando lo conocemos). None si no se ha verificado.
    """

    id: str = Field(description="Slug kebab-case unico.")
    nombre_canonico: str
    nombre_corto: str
    alias: List[str] = Field(default_factory=list)
    partido: str = ""
    posicion_tarjeton: Optional[int] = None
    plan_pdf: str = ""
    cne_organizacion_id: Optional[int] = None

    @property
    def consulta_secop(self) -> str:
        """Termino que SECOP/$q debe recibir para este candidato."""
        return self.nombre_canonico

    @property
    def consulta_datos_oficiales(self) -> str:
        """Termino para datos.gov.co (Procuraduria SIRI)."""
        return self.nombre_canonico

    @property
    def consulta_cne(self) -> str:
        """Termino para CNE: el partido es lo que la SPA del CNE indexa."""
        return self.partido or self.nombre_canonico

    @property
    def consulta_noticias(self) -> str:
        """Termino para Tavily/Serper. Nombre + partido si los dos existen."""
        if self.partido:
            return f"{self.nombre_corto} {self.partido}"
        return self.nombre_corto
