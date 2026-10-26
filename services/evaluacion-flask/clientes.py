"""Comunicación con catalogo-flask y trazos-flask por HTTP.

Mismo cliente que services/sesiones-flask/clientes.py (base de T16):

1. Timeout en cada petición (HTTP_TIMEOUT, 3 s por defecto).
2. Reintentos acotados con una espera corta y creciente, solo en GET
   (HTTP_REINTENTOS, 2 por defecto). Un POST no se reintenta.
3. Errores tipados:
   - `ServicioNoDisponible`: no respondió, tardó demasiado, respondió 5xx
     o algo que no es JSON;
   - `RespuestaRechazada`: respondió 4xx. Trae el estado y el JSON del
     error, porque acá un 404 del catálogo significa "ese carácter no
     existe" y un 400 de trazos significa "los puntos están mal".

A diferencia de sesiones-flask, evaluar no tiene respuesta degradada: si
falta una dependencia, el servicio responde 503 en vez de adivinar si la
respuesta del usuario era correcta.

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


class RespuestaRechazada(Exception):
    """El servicio respondió 4xx: la petición no se puede atender así."""

    def __init__(self, mensaje, estado, datos=None):
        super().__init__(mensaje)
        self.estado = estado
        self.datos = datos if isinstance(datos, dict) else {}


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


def _json_o_none(texto):
    try:
        return json.loads(texto)
    except ValueError:
        return None


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

        if 400 <= estado < 500:
            raise RespuestaRechazada(
                f"{metodo} {url}: respondió {estado}", estado, _json_o_none(texto)
            )
        if not 200 <= estado < 300:
            raise ServicioNoDisponible(f"{metodo} {url}: respondió {estado}", estado)
        datos = _json_o_none(texto)
        if datos is None:
            # Por ejemplo, la página HTML de un proxy caído.
            raise ServicioNoDisponible(f"{metodo} {url}: la respuesta no es JSON", estado)
        return datos

    def get(self, ruta, params=None):
        url = self._url(ruta, params)
        intentos = self.reintentos + 1
        for intento in range(1, intentos + 1):
            try:
                return self._una_vez("GET", url, None)
            except ServicioNoDisponible as error:
                # Un 4xx es RespuestaRechazada y no llega acá: no se reintenta.
                if intento == intentos:
                    raise
                logger.warning("Reintento %s de %s: %s", intento, url, error)
                self._dormir(self.espera * intento)

    def post(self, ruta, datos):
        cuerpo = json.dumps(datos).encode("utf-8")
        return self._una_vez("POST", self._url(ruta), cuerpo)


class CatalogoRemoto:
    """Detalle de un carácter en catalogo-flask (GET /api/v2/caracteres/<hanzi>/)."""

    def __init__(self, cliente):
        self._cliente = cliente

    def obtener_detalle(self, hanzi):
        ruta = f"/api/v2/caracteres/{urllib.parse.quote(hanzi, safe='')}/"
        return self._cliente.get(ruta)


class TrazosRemoto:
    """Comparación de un trazo en trazos-flask (POST /api/v2/trazos/validar/)."""

    def __init__(self, cliente):
        self._cliente = cliente

    def validar(self, mediana, puntos, ancho, alto):
        return self._cliente.post(
            "/api/v2/trazos/validar/",
            {"mediana": mediana, "puntos": puntos, "ancho": ancho, "alto": alto},
        )
