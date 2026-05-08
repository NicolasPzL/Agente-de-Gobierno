"""Tool real para SECOP I y II (datos.gov.co - Socrata).

Sprint 2: consulta los datasets configurados en `ATE_SECOP_II_DATASET`
y `ATE_SECOP_I_DATASET`. SECOP II tiene cobertura desde 2018; SECOP I
para historico previo. Se consultan en ese orden y se concatenan los
resultados.
"""

from __future__ import annotations

from typing import List, Optional

from ate.config.settings import Settings, load_settings
from ate.schemas.state import Intencion, ResultadoExtraccion
from ate.tools._http import HttpError, estado_desde_error
from ate.tools._socrata import consulta_socrata, url_dataset
from ate.tools.registry import ToolSpec, registrar

_NOMBRE = "consultar_secop"
_FUENTE = "SECOP I + SECOP II"


def consultar_secop(
    consulta: str,
    *,
    settings: Optional[Settings] = None,
) -> ResultadoExtraccion:
    """Consulta historial de contratacion publica en SECOP I y II.

    Args:
        consulta: texto libre. Tipicamente el nombre del proveedor /
            contratista / candidato. Se usa como `$q` (full-text).
        settings: snapshot opcional; si es None se carga desde entorno.
    """
    cfg = settings if settings is not None else load_settings()
    consulta = consulta.strip()

    if not consulta:
        urls_oficiales: List[str] = []
        if cfg.secop_ii_dataset:
            urls_oficiales.append(url_dataset(cfg.socrata_domain, cfg.secop_ii_dataset))
        if cfg.secop_i_dataset:
            urls_oficiales.append(url_dataset(cfg.socrata_domain, cfg.secop_i_dataset))
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="sin_datos",
            urls_oficiales=urls_oficiales,
            mensaje="Consulta vacia: no se invoco SECOP.",
        )

    if not cfg.secop_ii_dataset and not cfg.secop_i_dataset:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="no_configurado",
            mensaje=(
                "Ningun dataset SECOP configurado. Definir "
                "ATE_SECOP_II_DATASET y/o ATE_SECOP_I_DATASET en .env."
            ),
        )

    todas_filas: List[dict] = []
    urls: List[str] = []
    errores: List[tuple[str, HttpError]] = []   # (etiqueta, exc)

    for etiqueta, dataset in (
        ("SECOP II", cfg.secop_ii_dataset),
        ("SECOP I", cfg.secop_i_dataset),
    ):
        if not dataset:
            continue
        url_canonica = url_dataset(cfg.socrata_domain, dataset)
        urls.append(url_canonica)
        try:
            filas, _ = consulta_socrata(settings=cfg, dataset_id=dataset, q=consulta)
        except HttpError as exc:
            errores.append((etiqueta, exc))
            # Si la primera consulta cae offline, las siguientes tambien;
            # corte temprano para no acumular ruido.
            if exc.clase == "offline":
                return ResultadoExtraccion(
                    fuente=_FUENTE,
                    tool=_NOMBRE,
                    consulta=consulta,
                    estado="offline",
                    urls_oficiales=urls,
                    mensaje="ATE_OFFLINE=1: SECOP no consultado.",
                    error=str(exc),
                )
            continue
        # Anota la sub-fuente en cada fila para que sprint 4 distinga origen.
        for fila in filas:
            fila.setdefault("__sub_fuente__", etiqueta)
        todas_filas.extend(filas)

    if not todas_filas and errores:
        # Estado = el del primer error (todos los demas son del mismo orden).
        estado = estado_desde_error(errores[0][1])
        detalle = " | ".join(f"{etq}: {exc.clase} {exc.detalle[:140]}" for etq, exc in errores)
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado=estado,
            urls_oficiales=urls,
            mensaje="Ninguna consulta SECOP fue exitosa.",
            error=detalle,
        )

    if not todas_filas:
        return ResultadoExtraccion(
            fuente=_FUENTE,
            tool=_NOMBRE,
            consulta=consulta,
            estado="sin_datos",
            urls_oficiales=urls,
            mensaje="SECOP no devolvio coincidencias para la consulta.",
        )

    return ResultadoExtraccion(
        fuente=_FUENTE,
        tool=_NOMBRE,
        consulta=consulta,
        estado="ok",
        resultados=todas_filas,
        total_resultados=len(todas_filas),
        urls_oficiales=urls,
        mensaje=(
            f"SECOP devolvio {len(todas_filas)} contratos "
            f"({sum(1 for f in todas_filas if f.get('__sub_fuente__') == 'SECOP II')} en II, "
            f"{sum(1 for f in todas_filas if f.get('__sub_fuente__') == 'SECOP I')} en I) "
            f"para '{consulta}'."
            + (
                " Errores parciales: "
                + " | ".join(f"{etq}: {exc.clase}" for etq, exc in errores)
                if errores
                else ""
            )
        ),
    )


registrar(
    ToolSpec(
        nombre=_NOMBRE,
        descripcion=(
            "Consulta el historial de contratacion publica en SECOP I y SECOP II "
            "(Sistema Electronico para la Contratacion Publica)."
        ),
        intenciones=(Intencion.CONTRATACION,),
        ejecutar=consultar_secop,
        sprint_real=2,
    )
)
