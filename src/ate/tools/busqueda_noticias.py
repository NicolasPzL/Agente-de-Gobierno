"""Tool real de busqueda de noticias y declaraciones recientes.

Sprint 2: dos backends opcionales, despachados por `ATE_NEWS_PROVIDER`:
    - `tavily`: POST https://api.tavily.com/search  (requiere TAVILY_API_KEY)
    - `serper`: POST https://google.serper.dev/news (requiere SERPER_API_KEY)

Ambos requieren API key. Si no hay key configurada, la tool devuelve
estado `no_configurado` con un mensaje accionable. La eleccion de
proveedor es configuracion del usuario, no decision del agente — esto
preserva trazabilidad y reproducibilidad.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ate.config.settings import Settings, load_settings
from ate.schemas.state import Intencion, ResultadoExtraccion
from ate.tools._http import HttpError, estado_desde_error, http_post_json
from ate.tools.registry import ToolSpec, registrar

_NOMBRE = "buscar_noticias"
_FUENTE_TAVILY = "Tavily Search API"
_FUENTE_SERPER = "Serper.dev (Google News)"

_URL_TAVILY = "https://api.tavily.com/search"
_URL_SERPER = "https://google.serper.dev/news"


def _normalizar_resultados_tavily(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Tavily devuelve `{"results": [{"title", "url", "content", "score", "published_date"}]}`."""
    items = payload.get("results") or []
    normalizados: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalizados.append({
            "titulo": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
            "publicado": item.get("published_date", ""),
            "score": item.get("score"),
        })
    return normalizados


def _normalizar_resultados_serper(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Serper devuelve `{"news": [{"title", "link", "snippet", "date", "source"}]}`."""
    items = payload.get("news") or payload.get("organic") or []
    normalizados: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalizados.append({
            "titulo": item.get("title", ""),
            "url": item.get("link", ""),
            "snippet": item.get("snippet", ""),
            "publicado": item.get("date", ""),
            "fuente": item.get("source", ""),
        })
    return normalizados


def _consultar_tavily(consulta: str, cfg: Settings) -> ResultadoExtraccion:
    body = {
        "api_key": cfg.tavily_api_key,
        "query": f"{consulta} (Colombia elecciones 2026)",
        "search_depth": "basic",
        "topic": "news",
        "max_results": min(cfg.http_max_resultados, 10),
        "include_answer": False,
    }
    try:
        payload = http_post_json(_URL_TAVILY, settings=cfg, json_body=body)
    except HttpError as exc:
        return ResultadoExtraccion(
            fuente=_FUENTE_TAVILY,
            tool=_NOMBRE,
            consulta=consulta,
            estado=estado_desde_error(exc),
            mensaje=f"Tavily fallo: {exc.clase}.",
            error=str(exc),
        )

    items = _normalizar_resultados_tavily(payload if isinstance(payload, dict) else {})
    urls = [it["url"] for it in items if it.get("url")]
    if not items:
        return ResultadoExtraccion(
            fuente=_FUENTE_TAVILY,
            tool=_NOMBRE,
            consulta=consulta,
            estado="sin_datos",
            mensaje=f"Tavily no devolvio resultados para '{consulta}'.",
        )

    return ResultadoExtraccion(
        fuente=_FUENTE_TAVILY,
        tool=_NOMBRE,
        consulta=consulta,
        estado="ok",
        resultados=items,
        total_resultados=len(items),
        urls_oficiales=urls,
        mensaje=f"Tavily devolvio {len(items)} noticias para '{consulta}'.",
    )


def _consultar_serper(consulta: str, cfg: Settings) -> ResultadoExtraccion:
    body = {
        "q": f"{consulta} Colombia elecciones 2026",
        "gl": "co",
        "hl": "es",
        "num": min(cfg.http_max_resultados, 10),
    }
    headers = {"X-API-KEY": cfg.serper_api_key or ""}
    try:
        payload = http_post_json(
            _URL_SERPER, settings=cfg, json_body=body, headers=headers
        )
    except HttpError as exc:
        return ResultadoExtraccion(
            fuente=_FUENTE_SERPER,
            tool=_NOMBRE,
            consulta=consulta,
            estado=estado_desde_error(exc),
            mensaje=f"Serper fallo: {exc.clase}.",
            error=str(exc),
        )

    items = _normalizar_resultados_serper(payload if isinstance(payload, dict) else {})
    urls = [it["url"] for it in items if it.get("url")]
    if not items:
        return ResultadoExtraccion(
            fuente=_FUENTE_SERPER,
            tool=_NOMBRE,
            consulta=consulta,
            estado="sin_datos",
            mensaje=f"Serper no devolvio resultados para '{consulta}'.",
        )

    return ResultadoExtraccion(
        fuente=_FUENTE_SERPER,
        tool=_NOMBRE,
        consulta=consulta,
        estado="ok",
        resultados=items,
        total_resultados=len(items),
        urls_oficiales=urls,
        mensaje=f"Serper devolvio {len(items)} noticias para '{consulta}'.",
    )


def buscar_noticias(
    consulta: str,
    *,
    settings: Optional[Settings] = None,
) -> ResultadoExtraccion:
    """Busca noticias y declaraciones recientes via Tavily o Serper."""
    cfg = settings if settings is not None else load_settings()
    consulta = consulta.strip()

    if not consulta:
        return ResultadoExtraccion(
            fuente="Search API",
            tool=_NOMBRE,
            consulta=consulta,
            estado="sin_datos",
            mensaje="Consulta vacia: no se invoco buscador de noticias.",
        )

    provider = cfg.news_provider

    if provider == "none":
        return ResultadoExtraccion(
            fuente="Search API",
            tool=_NOMBRE,
            consulta=consulta,
            estado="no_configurado",
            mensaje=(
                "ATE_NEWS_PROVIDER=none. Para habilitar busqueda de noticias, "
                "fijar ATE_NEWS_PROVIDER=tavily (o serper) y la API key "
                "correspondiente en .env."
            ),
        )

    if provider == "tavily":
        if not cfg.tavily_api_key:
            return ResultadoExtraccion(
                fuente=_FUENTE_TAVILY,
                tool=_NOMBRE,
                consulta=consulta,
                estado="no_configurado",
                mensaje=(
                    "TAVILY_API_KEY no configurada. Obtenerla gratis en "
                    "https://app.tavily.com y agregarla a .env."
                ),
            )
        return _consultar_tavily(consulta, cfg)

    if provider == "serper":
        if not cfg.serper_api_key:
            return ResultadoExtraccion(
                fuente=_FUENTE_SERPER,
                tool=_NOMBRE,
                consulta=consulta,
                estado="no_configurado",
                mensaje=(
                    "SERPER_API_KEY no configurada. Obtenerla en "
                    "https://serper.dev y agregarla a .env."
                ),
            )
        return _consultar_serper(consulta, cfg)

    # Defensivo: load_settings ya valida valores, pero por si se construye Settings a mano.
    return ResultadoExtraccion(
        fuente="Search API",
        tool=_NOMBRE,
        consulta=consulta,
        estado="no_configurado",
        mensaje=f"news_provider desconocido: {provider!r}",
    )


registrar(
    ToolSpec(
        nombre=_NOMBRE,
        descripcion=(
            "Busca noticias y declaraciones recientes sobre un candidato "
            "o tema mediante Tavily o Serper."
        ),
        intenciones=(Intencion.NOTICIAS,),
        ejecutar=buscar_noticias,
        sprint_real=2,
    )
)
