"""Configuracion del sistema cargada desde variables de entorno.

Sprint 1: lee proveedor de LLM y credenciales (planificador).
Sprint 2: agrega configuracion para tools reales contra APIs oficiales
(Socrata datos.gov.co / SECOP, CNE Cuentas Claras, Tavily / Serper) y un
flag global `ate_offline` que fuerza a las tools a no tocar la red. Los
tests forzan `ate_offline=True` desde `conftest.py` como red de seguridad
adicional al monkeypatch de HTTP.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

Provider = Literal["anthropic", "openai", "ollama", "none"]
_PROVIDERS_VALIDOS = ("anthropic", "openai", "ollama", "none")

# Defaults publicos. Cualquiera puede sobreescribirlos por env var sin
# tocar codigo. Los IDs de dataset por defecto apuntan a recursos que han
# sido publicos historicamente; si datos.gov.co cambia el slug, basta
# con ajustar la env var correspondiente.
_DEFAULT_SOCRATA_DOMAIN = "www.datos.gov.co"
_DEFAULT_SECOP_II_DATASET = "jbjy-vk9h"           # SECOP II - Contratos Electronicos
_DEFAULT_SECOP_I_DATASET = "f789-7hwg"            # SECOP I - Contratos
_DEFAULT_SANCIONES_DATASET = "iaeu-rcn6"          # Procuraduria - Antecedentes SIRI (verificado activo)
_DEFAULT_CNE_DATASET = ""                          # No hay dataset estable Socrata; opt-in

_DEFAULT_NEWS_PROVIDER = "tavily"


@dataclass(frozen=True)
class Settings:
    """Snapshot inmutable de la configuracion al momento de la carga."""

    # --- LLM (Sprint 1) ---
    llm_provider: Provider
    anthropic_api_key: str | None
    anthropic_model: str
    openai_api_key: str | None
    openai_model: str
    ollama_host: str
    ollama_model: str
    ollama_timeout: float

    # --- HTTP / red (Sprint 2) ---
    ate_offline: bool
    http_timeout: float
    http_max_resultados: int

    # --- Socrata / datos.gov.co (Sprint 2) ---
    socrata_domain: str
    socrata_app_token: str | None
    secop_ii_dataset: str
    secop_i_dataset: str
    sanciones_dataset: str

    # --- CNE Cuentas Claras (Sprint 2) ---
    cne_dataset: str          # ID Socrata; "" si no se configuro un dataset estable.
    cne_csv_url: str          # URL CSV / endpoint alterno; "" si no se configuro.
    cne_use_api: bool         # Activa el cliente contra la API publica de la SPA CNE 2026.

    # --- Buscadores de noticias (Sprint 2) ---
    news_provider: Literal["tavily", "serper", "none"]
    tavily_api_key: str | None
    serper_api_key: str | None

    # --- Comportamiento del agente extraccion (Sprint 2) ---
    extraccion_max_tools: int

    # --- RAG sobre planes de gobierno (Sprint 3) ---
    rag_dir: str            # carpeta raiz de persistencia (Chroma vive en <rag_dir>/chroma).
    rag_top_k: int          # cuantos pasajes recuperar por consulta.
    rag_chunk_size: int     # tamano de chunk en caracteres (para el ingestor).
    rag_chunk_overlap: int  # solapamiento entre chunks (caracteres).

    # ------------------------------------------------------------------
    # Helpers derivados
    # ------------------------------------------------------------------

    @property
    def llm_available(self) -> bool:
        """True si el proveedor configurado tiene credenciales para operar.

        Ollama no tiene "credencial" propiamente — asumimos que el usuario
        ejecuto `ollama serve` localmente. La disponibilidad real se
        detecta al invocar; aqui solo decimos "intenta usarlo".
        """
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        if self.llm_provider == "ollama":
            return bool(self.ollama_model)
        return False

    @property
    def news_api_disponible(self) -> bool:
        """True si hay credencial para el proveedor de noticias activo."""
        if self.news_provider == "tavily":
            return bool(self.tavily_api_key)
        if self.news_provider == "serper":
            return bool(self.serper_api_key)
        return False


def _bool(env: str, default: bool = False) -> bool:
    raw = os.getenv(env)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "si")


def _int(env: str, default: int) -> int:
    raw = os.getenv(env)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{env} debe ser entero: {exc}") from exc


def _float(env: str, default: float) -> float:
    raw = os.getenv(env)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{env} debe ser numerico: {exc}") from exc


def load_settings() -> Settings:
    """Carga la configuracion desde `.env` + entorno.

    Falla rapido con un mensaje claro si `ATE_LLM_PROVIDER` o
    `ATE_NEWS_PROVIDER` tienen un valor no soportado; no valida
    credenciales aqui — eso se verifica en el punto de uso.
    """
    load_dotenv()  # idempotente; no sobreescribe variables ya exportadas

    provider_raw = (os.getenv("ATE_LLM_PROVIDER") or "none").strip().lower()
    if provider_raw not in _PROVIDERS_VALIDOS:
        raise ValueError(
            f"ATE_LLM_PROVIDER invalido: {provider_raw!r}. "
            f"Valores soportados: {', '.join(_PROVIDERS_VALIDOS)}."
        )

    news_raw = (os.getenv("ATE_NEWS_PROVIDER") or _DEFAULT_NEWS_PROVIDER).strip().lower()
    if news_raw not in ("tavily", "serper", "none"):
        raise ValueError(
            f"ATE_NEWS_PROVIDER invalido: {news_raw!r}. "
            "Valores soportados: tavily, serper, none."
        )

    return Settings(
        # --- LLM ---
        llm_provider=provider_raw,  # type: ignore[arg-type]
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        anthropic_model=os.getenv("ATE_ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("ATE_OPENAI_MODEL", "gpt-4o"),
        ollama_host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        ollama_timeout=_float("OLLAMA_TIMEOUT", 60.0),

        # --- HTTP ---
        ate_offline=_bool("ATE_OFFLINE", default=False),
        http_timeout=_float("ATE_HTTP_TIMEOUT", 20.0),
        http_max_resultados=_int("ATE_MAX_RESULTADOS", 25),

        # --- Socrata ---
        socrata_domain=os.getenv("SOCRATA_DOMAIN", _DEFAULT_SOCRATA_DOMAIN).strip().rstrip("/"),
        socrata_app_token=os.getenv("SOCRATA_APP_TOKEN") or None,
        secop_ii_dataset=os.getenv("ATE_SECOP_II_DATASET", _DEFAULT_SECOP_II_DATASET).strip(),
        secop_i_dataset=os.getenv("ATE_SECOP_I_DATASET", _DEFAULT_SECOP_I_DATASET).strip(),
        sanciones_dataset=os.getenv("ATE_SANCIONES_DATASET", _DEFAULT_SANCIONES_DATASET).strip(),

        # --- CNE ---
        cne_dataset=os.getenv("ATE_CNE_DATASET", _DEFAULT_CNE_DATASET).strip(),
        cne_csv_url=os.getenv("ATE_CNE_CSV_URL", "").strip(),
        cne_use_api=_bool("ATE_CNE_USE_API", default=True),

        # --- Buscadores ---
        news_provider=news_raw,  # type: ignore[arg-type]
        tavily_api_key=os.getenv("TAVILY_API_KEY") or None,
        serper_api_key=os.getenv("SERPER_API_KEY") or None,

        # --- Extraccion ---
        extraccion_max_tools=_int("ATE_EXTRACCION_MAX_TOOLS", 5),

        # --- RAG ---
        rag_dir=os.getenv("ATE_RAG_DIR", "data/rag").strip(),
        rag_top_k=_int("ATE_RAG_TOP_K", 5),
        rag_chunk_size=_int("ATE_RAG_CHUNK_SIZE", 800),
        rag_chunk_overlap=_int("ATE_RAG_CHUNK_OVERLAP", 120),
    )
