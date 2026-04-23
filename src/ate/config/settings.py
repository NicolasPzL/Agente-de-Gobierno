"""Configuracion del sistema cargada desde variables de entorno.

Sprint 1 lee el proveedor de LLM y sus credenciales. Si el proveedor es
`none` (por defecto), el planificador usa clasificacion determinista por
palabras clave y no requiere API keys ni red.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

Provider = Literal["anthropic", "openai", "ollama", "none"]
_PROVIDERS_VALIDOS = ("anthropic", "openai", "ollama", "none")


@dataclass(frozen=True)
class Settings:
    """Snapshot inmutable de la configuracion al momento de la carga."""

    llm_provider: Provider
    anthropic_api_key: str | None
    anthropic_model: str
    openai_api_key: str | None
    openai_model: str
    ollama_host: str
    ollama_model: str
    ollama_timeout: float

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


def load_settings() -> Settings:
    """Carga la configuracion desde `.env` + entorno.

    Falla rapido con un mensaje claro si `ATE_LLM_PROVIDER` tiene un valor
    no soportado; no valida credenciales aqui — eso se verifica en el
    punto de uso (clasificador LLM).
    """
    load_dotenv()  # idempotente; no sobreescribe variables ya exportadas

    provider_raw = (os.getenv("ATE_LLM_PROVIDER") or "none").strip().lower()
    if provider_raw not in _PROVIDERS_VALIDOS:
        raise ValueError(
            f"ATE_LLM_PROVIDER invalido: {provider_raw!r}. "
            f"Valores soportados: {', '.join(_PROVIDERS_VALIDOS)}."
        )

    try:
        ollama_timeout = float(os.getenv("OLLAMA_TIMEOUT", "60"))
    except ValueError as exc:
        raise ValueError(f"OLLAMA_TIMEOUT debe ser numerico: {exc}") from exc

    return Settings(
        llm_provider=provider_raw,  # type: ignore[arg-type]
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        anthropic_model=os.getenv("ATE_ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("ATE_OPENAI_MODEL", "gpt-4o"),
        ollama_host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        ollama_timeout=ollama_timeout,
    )
