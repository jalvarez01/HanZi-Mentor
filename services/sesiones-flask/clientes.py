"""Comunicación con otros servicios por HTTP (base de T16).

sesiones-flask nunca importa código ni lee la base de otro servicio: pide
lo que necesita por HTTP con `ClienteHttp`, que aplica tres reglas:

1. Timeout en cada petición (HTTP_TIMEOUT, 3 s por defecto).
2. Reintentos acotados con una espera corta y creciente, solo en GET
   (HTTP_REINTENTOS, 2 por defecto). Un POST no se reintenta: podría
   registrar dos veces la misma respuesta.
3. Si el servicio no responde, devuelve un error tipado
   (`ServicioNoDisponible`) y cada cliente decide la respuesta degradada:
   - catálogo caído: lista local chica de caracteres por nivel HSK;
   - GET de progreso caído: valores iniciales del progreso;
   - POST de progreso caído: None, y la ruta agrega un aviso.

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


# ---------------------------------------------------------------- catálogo


class CatalogoLocal:
    """Respaldo en memoria cuando el catálogo no responde (igual que v1)."""

    POR_NIVEL = {
        1: ["人", "口", "日", "月", "水", "火", "山", "大", "小", "中"],
        2: ["学", "校", "老", "师", "同", "朋", "友", "书", "本", "笔"],
        3: ["经", "济", "政", "府", "社", "会", "文", "化", "历", "史"],
        4: ["环", "境", "资", "源", "技", "术", "发", "展", "研", "究"],
        5: ["哲", "学", "逻", "辑", "概", "念", "理", "论", "思", "维"],
        6: ["宪", "法", "司", "立", "权", "利", "义", "务", "制", "度"],
    }

    def caracteres_de_nivel(self, nivel, excluir=None, cantidad=4):
        omitir = set(excluir or [])
        disponibles = self.POR_NIVEL.get(nivel, [])
        return [c for c in disponibles if c not in omitir][:cantidad]


class CatalogoRemoto:
    """Caracteres nuevos desde catalogo-flask (GET /api/v2/caracteres/)."""

    def __init__(self, cliente, respaldo=None):
        self._cliente = cliente
        self._respaldo = respaldo or CatalogoLocal()

    def caracteres_de_nivel(self, nivel, excluir=None, cantidad=4):
        omitir = list(excluir or [])
        try:
            datos = self._cliente.get(
                "/api/v2/caracteres/",
                {"nivel": nivel, "excluir": ",".join(omitir), "limite": cantidad},
            )
            hanzi = [d["hanzi"] for d in datos.get("caracteres", []) if d.get("hanzi")]
            if hanzi:
                return hanzi[:cantidad]
            logger.warning("El catálogo no devolvió caracteres de HSK%s", nivel)
        except (ServicioNoDisponible, AttributeError, KeyError, TypeError) as error:
            logger.warning("Catálogo no disponible, se usa la lista local: %s", error)
        return self._respaldo.caracteres_de_nivel(nivel, omitir, cantidad)


# ---------------------------------------------------------------- progreso


def progreso_inicial(usuario_id):
    """Los valores de un usuario nuevo, iguales a los de progreso-flask."""
    return {
        "usuario_id": str(usuario_id),
        "nivel_hsk": 1,
        "nivel_max_desbloqueado": 1,
        "tasa_acierto": 0.5,
        "caracteres_dominados": [],
        "errores_frecuentes": {},
        "aciertos_consecutivos": {},
        "proximo_repaso": None,
        "actualizado_en": None,
        "total_dominados": 0,
        "total_por_reforzar": 0,
        "caracteres_debiles": [],
    }


class ProgresoRemoto:
    """Progreso del usuario en progreso-flask (/api/v2/progreso/...)."""

    def __init__(self, cliente):
        self._cliente = cliente

    def obtener(self, usuario_id):
        try:
            return self._cliente.get(f"/api/v2/progreso/{usuario_id}/")
        except ServicioNoDisponible as error:
            logger.warning("Progreso no disponible, se usan valores iniciales: %s", error)
            return progreso_inicial(usuario_id)

    def caracteres_a_reforzar(self, usuario_id, limite=3):
        try:
            datos = self._cliente.get(
                f"/api/v2/progreso/{usuario_id}/refuerzos/", {"limite": limite}
            )
            return list(datos.get("caracteres", []))[:limite]
        except (ServicioNoDisponible, AttributeError, TypeError) as error:
            logger.warning("Refuerzos no disponibles, la sesión va sin refuerzos: %s", error)
            return []

    def registrar_respuesta(self, usuario_id, caracter, acerto):
        """Devuelve el progreso actualizado, o None si progreso-flask no respondió."""
        try:
            return self._cliente.post(
                f"/api/v2/progreso/{usuario_id}/respuestas/",
                {"caracter": caracter, "acerto": acerto},
            )
        except ServicioNoDisponible as error:
            logger.warning("No se pudo registrar la respuesta en progreso: %s", error)
            return None
