"""Comunicación con progreso-flask por HTTP.

`ClienteHttp` es el mismo de services/sesiones-flask/clientes.py (base de
T16): timeout en cada petición, reintentos acotados solo en GET y errores
tipados (`ServicioNoDisponible`).

Diferencia con sesiones-flask: un reporte no tiene respuesta degradada. Si
progreso no responde, `ProgresoRemoto` lanza el error y la tarea lo
reintenta con Celery; nunca devuelve valores iniciales como si fueran el
progreso real.

Solo se usa la biblioteca estándar (urllib).
"""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from http.client import HTTPException

logger = logging.getLogger(__name__)


class ServicioNoDisponible(Exception):
    """El servicio no respondió, tardó demasiado o respondió algo inválido."""

    def __init__(self, mensaje, estado=None):
        super().__init__(mensaje)
        self.estado = estado


def transporte_urllib(metodo, url, cuerpo, timeout):
    """Hace la petición y devuelve (estado, texto). Un 4xx o 5xx no es excepción."""
    cabeceras = {"Accept": "application/json"}
    if cuerpo is not None:
        cabeceras["Content-Type"] = "application/json"
    peticion = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            return respuesta.status, respuesta.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


class ClienteHttp:
    """Cliente JSON con timeout, reintentos en GET y errores tipados."""

    def __init__(self, base_url, timeout=3.0, reintentos=2, espera=0.2,
                 transporte=transporte_urllib, dormir=time.sleep):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.reintentos = reintentos
        self.espera = espera
        self._transporte = transporte
        self._dormir = dormir

    def _url(self, ruta, params=None):
        url = f"{self.base_url}{ruta}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return url

    def _una_vez(self, metodo, url, cuerpo):
        try:
            estado, texto = self._transporte(metodo, url, cuerpo, self.timeout)
        except (OSError, HTTPException) as error:
            # Conexión rechazada, DNS, timeout (TimeoutError es OSError).
            raise ServicioNoDisponible(f"{metodo} {url}: {error}") from None

        if not 200 <= estado < 300:
            raise ServicioNoDisponible(f"{metodo} {url}: respondió {estado}", estado)
        try:
            return json.loads(texto)
        except ValueError:
            # Por ejemplo, la página HTML de un proxy caído.
            raise ServicioNoDisponible(f"{metodo} {url}: la respuesta no es JSON", estado) from None

    def get(self, ruta, params=None):
        url = self._url(ruta, params)
        intentos = self.reintentos + 1
        for intento in range(1, intentos + 1):
            try:
                return self._una_vez("GET", url, None)
            except ServicioNoDisponible as error:
                # Un 4xx no cambia reintentando: es la petición la que está mal.
                es_4xx = error.estado is not None and 400 <= error.estado < 500
                if es_4xx or intento == intentos:
                    raise
                logger.warning("Reintento %s de %s: %s", intento, url, error)
                self._dormir(self.espera * intento)

    def post(self, ruta, datos):
        cuerpo = json.dumps(datos).encode("utf-8")
        return self._una_vez("POST", self._url(ruta), cuerpo)


class ProgresoRemoto:
    """Progreso del usuario en progreso-flask (GET /api/v2/progreso/<id>/)."""

    def __init__(self, cliente):
        self._cliente = cliente

    def obtener(self, usuario_id):
        """Devuelve el dict del progreso o lanza ServicioNoDisponible."""
        datos = self._cliente.get(f"/api/v2/progreso/{usuario_id}/")
        if not isinstance(datos, dict):
            raise ServicioNoDisponible("progreso no devolvió un objeto JSON")
        return datos
