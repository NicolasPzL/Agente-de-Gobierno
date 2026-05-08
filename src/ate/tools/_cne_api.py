"""Cliente para la API publica del CNE 2026 (Cuentas Claras / Fondo CNG 2026).

La aplicacion del CNE para las elecciones 2026 (`app_cng_2026.cne.gov.co`)
es una SPA Laravel + Vue. No expone API documentada, pero hace todas
sus llamadas via XHR contra rutas REST que SI son publicas:

    GET  /consultar/selecOganizacionPoliticaPublic   -> organizaciones politicas
    GET  /consultar/selectAniosPublic                -> anios disponibles
    GET  /getProcesosElectoralesPublic               -> procesos electorales
    GET  /getTipoEleccionPublic                      -> tipos de eleccion
    GET  /getCorporacionPublic/{tipo}/{proceso}      -> corporaciones
    GET  /getTipoCircunscripcionPublic/{corp}        -> circunscripciones
    GET  /departamentoPublic/selectDepartamento      -> departamentos
    GET  /getCiudadPublic/{depto}                    -> municipios
    GET  /anhosProcesos                              -> anios con procesos
    PUT  /candidatos/getcandidatos                   -> candidatos por filtros
    POST /consultar/informePublico                   -> ingresos/gastos del candidato
    POST /consultar/informeConsultaOrganizacion      -> ingresos/gastos de la organizacion
    POST /informes/trazabilidad                      -> trazabilidad por cedula+id_cuenta

Las rutas POST/PUT requieren CSRF (Laravel). Este cliente:
    1. Hace GET inicial para obtener cookies (`XSRF-TOKEN`, `cne_session`).
    2. Decodifica `XSRF-TOKEN` (URL-decode) y la envia como header
       `X-XSRF-TOKEN`.
    3. Mantiene la sesion via `requests.Session`.

NOTA importante: la app no expone busqueda libre por nombre. La SPA
filtra por jerarquia (proceso -> tipo -> corporacion -> ... -> candidato).
Esto significa que la mejor consulta libre que podemos ofrecer en
Sprint 2 es:
    - Listar PROCESOS ELECTORALES 2026 disponibles.
    - Listar ORGANIZACIONES POLITICAS registradas.
    - Match por substring contra nombres de organizacion.
    - Si la query es una cedula, intentar la trazabilidad por cedula.

Si los datos individuales de candidato aun no estan registrados (lo
cual es normal en periodo previo al cierre de campana), la tool
devuelve `sin_datos` con la lista de procesos como referencia. NUNCA
inventa donantes ni montos.
"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Dict, List, Optional

import requests
from requests import RequestException

from ate.config.settings import Settings

logger = logging.getLogger(__name__)


# URLs canonicas para citacion en `urls_oficiales`.
URL_PORTAL = "https://www.cnecuentasclaras.gov.co/"
URL_APP_PUBLIC = "https://app_cng_2026.cne.gov.co/fondo_cng_2026/public/informes/cne"
BASE_API = "https://app_cng_2026.cne.gov.co/fondo_cng_2026/public"


class CneApiError(Exception):
    """Error generico del cliente CNE."""


class CneApiClient:
    """Cliente con sesion + CSRF para la SPA Laravel del CNE 2026."""

    def __init__(self, *, settings: Settings, base_url: str = BASE_API):
        self.settings = settings
        self.base_url = base_url.rstrip("/")
        self._sesion: Optional[requests.Session] = None

    # --------------------------- sesion / CSRF ---------------------------

    def _nueva_sesion(self) -> requests.Session:
        s = requests.Session()
        s.verify = False    # los certificados del CNE fallan validacion estandar
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ATE/0.2; +https://github.com/MateoGiraldoT/agenteGobierno)",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        })
        return s

    def _asegurar_sesion(self) -> requests.Session:
        """Lazy-init de la sesion + obtencion de XSRF-TOKEN."""
        if self._sesion is not None:
            return self._sesion
        s = self._nueva_sesion()
        # GET inicial para que el servidor devuelva XSRF-TOKEN + cne_session.
        try:
            s.get(
                f"{self.base_url}/informes/cne",
                timeout=self.settings.http_timeout,
            )
        except RequestException as exc:
            raise CneApiError(f"No se pudo iniciar sesion CNE: {exc}") from exc

        xsrf = s.cookies.get("XSRF-TOKEN")
        if xsrf:
            # Laravel: el cookie esta URL-encoded; el header debe ir decoded.
            s.headers["X-XSRF-TOKEN"] = urllib.parse.unquote(xsrf)
        self._sesion = s
        return s

    # --------------------------- HTTP wrappers ---------------------------

    def _get(self, path: str) -> Any:
        s = self._asegurar_sesion()
        url = f"{self.base_url}{path}"
        try:
            r = s.get(url, timeout=self.settings.http_timeout)
        except RequestException as exc:
            raise CneApiError(f"GET {path} fallo: {exc}") from exc
        if r.status_code >= 400:
            raise CneApiError(f"GET {path} -> HTTP {r.status_code}")
        try:
            return r.json()
        except ValueError as exc:
            raise CneApiError(f"GET {path}: respuesta no-JSON") from exc

    def _post(self, path: str, payload: Dict[str, Any]) -> Any:
        s = self._asegurar_sesion()
        url = f"{self.base_url}{path}"
        try:
            r = s.post(url, json=payload, timeout=self.settings.http_timeout)
        except RequestException as exc:
            raise CneApiError(f"POST {path} fallo: {exc}") from exc
        if r.status_code >= 400:
            raise CneApiError(f"POST {path} -> HTTP {r.status_code}: {r.text[:200]}")
        try:
            return r.json()
        except ValueError as exc:
            raise CneApiError(f"POST {path}: respuesta no-JSON") from exc

    def _put(self, path: str, payload: Dict[str, Any]) -> Any:
        s = self._asegurar_sesion()
        url = f"{self.base_url}{path}"
        try:
            r = s.put(url, json=payload, timeout=self.settings.http_timeout)
        except RequestException as exc:
            raise CneApiError(f"PUT {path} fallo: {exc}") from exc
        if r.status_code >= 400:
            raise CneApiError(f"PUT {path} -> HTTP {r.status_code}: {r.text[:200]}")
        try:
            return r.json()
        except ValueError as exc:
            raise CneApiError(f"PUT {path}: respuesta no-JSON") from exc

    # --------------------------- endpoints ---------------------------

    def listar_procesos_electorales(self) -> List[Dict[str, Any]]:
        return self._get("/getProcesosElectoralesPublic") or []

    def listar_organizaciones_politicas(self) -> List[Dict[str, Any]]:
        data = self._get("/consultar/selecOganizacionPoliticaPublic") or {}
        return data.get("organizaciones", []) if isinstance(data, dict) else []

    def listar_tipos_eleccion(self) -> List[Dict[str, Any]]:
        return self._get("/getTipoEleccionPublic") or []

    def listar_corporaciones(self, tipo_proceso: int, proceso_electoral: int) -> List[Dict[str, Any]]:
        return self._get(f"/getCorporacionPublic/{tipo_proceso}/{proceso_electoral}") or []

    def listar_candidatos(
        self,
        *,
        proceso: int,
        tipo_proceso: int,
        corporacion: int = 0,
        circunscripcion: int = 0,
        departamento: int = 0,
        municipio: int = 0,
        tipo_org: int = 0,
        organizacion: int = 0,
    ) -> List[Dict[str, Any]]:
        payload = {
            "idProceso": proceso,
            "idTipo_proceso": tipo_proceso,
            "idCorporacion": corporacion,
            "idCircunscripcion": circunscripcion,
            "idDepartamento": departamento,
            "idMunicipio": municipio,
            "tipo_org": tipo_org,
            "organizaciones": organizacion,
        }
        out = self._put("/candidatos/getcandidatos", payload)
        return out if isinstance(out, list) else []

    def informe_publico_candidato(
        self,
        *,
        id_candidato: Any,
        proceso_electoral: int,
        tipo_proceso: int,
        tipo_org: int,
        organizacion: int,
        corporacion: int,
        circunscripcion: int,
        departamento: int,
        municipio: int,
    ) -> Dict[str, Any]:
        """POST /consultar/informePublico — ingresos/gastos/obligaciones."""
        payload = {
            "candidato": id_candidato,
            "proceso_electoral": proceso_electoral,
            "tipoProceso": tipo_proceso,
            "tipo_org": tipo_org,
            "organizaciones": organizacion,
            "corporacion": corporacion,
            "circunscripcion": circunscripcion,
            "departamento": departamento,
            "municipio": municipio,
        }
        out = self._post("/consultar/informePublico", payload)
        return out if isinstance(out, dict) else {}

    def trazabilidad_por_cedula(self, *, cedula: str, id_cuenta: str = "") -> Dict[str, Any]:
        """POST /informes/trazabilidad — requiere cedula + id_cuenta.

        Si `id_cuenta` queda vacio, la API tiende a fallar; el caller
        debe haberlo obtenido antes via `listar_candidatos`.
        """
        out = self._post(
            "/informes/trazabilidad",
            {"cedula": cedula, "id_cuenta": id_cuenta},
        )
        return out if isinstance(out, dict) else {}
