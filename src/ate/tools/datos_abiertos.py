"""Tool real para el Portal de Datos Abiertos (datos.gov.co).

Sprint 2: consulta el dataset Socrata configurado en `ATE_SANCIONES_DATASET`
(default: Procuraduria - Sanciones e inhabilidades) usando full-text
search sobre la consulta del usuario.

La tool conserva la firma `(consulta: str) -> ResultadoExtraccion` y el
agente de extraccion la invoca igual que en Sprint 1; lo unico que
cambio es el cuerpo y el shape (`dict` -> `ResultadoExtraccion`).
"""

from __future__ import annotations

from typing import Optional

from ate.config.settings import Settings, load_settings
from ate.schemas.state import Intencion, ResultadoExtraccion
from ate.tools._http import HttpError, estado_desde_error
from ate.tools._socrata import consulta_socrata, url_dataset
from ate.tools.registry import ToolSpec, registrar

_NOMBRE = "consultar_datos_abiertos"
_FUENTE = "datos.gov.co - Sanciones / Procuraduria"


def consultar_datos_abiertos(
    consulta: str,
    *,
    settings: Optional[Settings] = None,
) -> ResultadoExtraccion:
    """Consulta sanciones, multas y procesos en datos.gov.co (Socrata).

    Args:
        consulta: texto libre (nombre del candidato o de una entidad).
        settings: snapshot opcional; si es None se carga desde entorno.

    Returns:
        `ResultadoExtraccion` con filas crudas en `resultados` y la URL
        canonica del dataset en `urls_oficiales` para citacion.
    """
    cfg = settings if settings is not None else load_settings()
    consulta = consulta.strip()
    dataset = cfg.sanciones_dataset

    if not dataset:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="no_configurado",
            mensaje=(
                "ATE_SANCIONES_DATASET vacio. Configurar el ID Socrata "
                "del dataset de sanciones en .env (ver .env.example)."
            ),
        )

    if not consulta:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="sin_datos",
            mensaje="Consulta vacia: no se invoco el endpoint.",
            urls_oficiales=[url_dataset(cfg.socrata_domain, dataset)],
        )

    try:
        filas, url_oficial = consulta_socrata(
            settings=cfg, dataset_id=dataset, q=consulta
        )
    except HttpError as exc:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado=estado_desde_error(exc),
            urls_oficiales=[url_dataset(cfg.socrata_domain, dataset)],
            mensaje=f"No se pudo consultar datos.gov.co: {exc.clase}.",
            error=str(exc),
        )

    if not filas:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="sin_datos",
            urls_oficiales=[url_oficial],
            mensaje="datos.gov.co no devolvio coincidencias para la consulta.",
        )

    return ResultadoExtraccion(
        fuente=_FUENTE,
        tool=_NOMBRE,
        consulta=consulta,
        estado="ok",
        resultados=filas,
        total_resultados=len(filas),
        urls_oficiales=[url_oficial],
        mensaje=(
            f"datos.gov.co devolvio {len(filas)} registros para "
            f"'{consulta}'. Revise `resultados[].*` para los campos crudos."
        ),
    )


registrar(
    ToolSpec(
        nombre=_NOMBRE,
        descripcion=(
            "Consulta sanciones, multas y procesos disciplinarios/fiscales/penales "
            "registrados en el Portal de Datos Abiertos (datos.gov.co)."
        ),
        intenciones=(Intencion.DATOS_OFICIALES,),
        ejecutar=consultar_datos_abiertos,
        sprint_real=2,
    )
)
