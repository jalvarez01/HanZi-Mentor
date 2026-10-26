"""Adaptador real: oraciones de ejemplo de la API pública de Tatoeba.

Usa el endpoint estable GET /v1/sentences (https://api.tatoeba.org), que no
requiere clave. Traduce la respuesta de Tatoeba al modelo del dominio
(`Ejemplo`) y convierte cualquier falla de red o de formato en
`ProveedorNoDisponible`, para que el caso de uso no conozca nada de HTTP.
"""

import html
import http.client
import json
import re
import urllib.parse
import urllib.request

from dominio.ejemplo import Ejemplo
from dominio.puertos import ProveedorEjemplos, ProveedorNoDisponible
from mensajes import N_

# Idioma del dominio -> código ISO 639-3 que usa Tatoeba.
_IDIOMAS = {"es": "spa", "en": "eng"}
_ETIQUETAS = re.compile(r"<[^>]+>")
_AGENTE = "HanZi-Mentor/1.0 (proyecto académico, Universidad EAFIT)"


def obtener_json(url, timeout):
    """GET que devuelve el JSON de la respuesta. Lanza ProveedorNoDisponible."""
    peticion = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": _AGENTE}
    )
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            return json.load(respuesta)
    except (OSError, http.client.HTTPException, ValueError) as error:
        # OSError cubre URLError/HTTPError (4xx/5xx), timeouts y conexiones
        # cortadas; HTTPException, respuestas incompletas; ValueError, JSON inválido.
        raise ProveedorNoDisponible(f"Tatoeba no respondió: {error}") from error


class AdaptadorTatoeba(ProveedorEjemplos):
    nombre = "tatoeba"
    # Texto para personas: se traduce al responder (ver rutas.py).
    atribucion = N_("Oraciones de Tatoeba.org (CC BY 2.0 FR)")

    def __init__(self, url_base, timeout, obtener=obtener_json):
        self._url_base = url_base.rstrip("/")
        self._timeout = timeout
        # Inyectable para probar el adaptador sin salir a internet.
        self._obtener = obtener

    def obtener(self, hanzi, idioma, limite):
        # Primero solo oraciones con traducción directa. Las indirectas pasan
        # por un tercer idioma y pierden sentido en cada salto (等一下, "espera
        # un momento", llegaba como "Err..."). Si no hay ninguna directa, se
        # aceptan indirectas para que el carácter no se quede sin ejemplos.
        ejemplos = self._buscar(hanzi, idioma, limite, solo_directas=True)
        if not ejemplos:
            ejemplos = self._buscar(hanzi, idioma, limite, solo_directas=False)
        return ejemplos

    def _buscar(self, hanzi, idioma, limite, solo_directas):
        # Se pide el doble porque Tatoeba repite frases (la misma en
        # tradicional y en simplificado) y las repetidas se descartan.
        url = self._url(hanzi, idioma, limite * 2, solo_directas)
        datos = self._obtener(url, self._timeout)
        try:
            ejemplos = [self._a_ejemplo(oracion, _IDIOMAS[idioma]) for oracion in datos["data"]]
        except (KeyError, TypeError, AttributeError) as error:
            raise ProveedorNoDisponible(f"Respuesta de Tatoeba inesperada: {error!r}") from error

        unicos = {}
        for ejemplo in ejemplos:
            unicos.setdefault(ejemplo.texto, ejemplo)
        return list(unicos.values())[:limite]

    def _url(self, hanzi, idioma, limite, solo_directas=True):
        parametros = {
            "lang": "cmn",
            # Entre comillas: frase exacta en la sintaxis de búsqueda de Tatoeba.
            "q": f'"{hanzi}"',
            # Solo oraciones que tengan traducción al idioma pedido.
            "trans:lang": _IDIOMAS[idioma],
            "sort": "relevance",
            "limit": limite,
            "include": "transcriptions",
        }
        if solo_directas:
            parametros["trans:is_direct"] = "yes"
        return f"{self._url_base}/v1/sentences?{urllib.parse.urlencode(parametros)}"

    @staticmethod
    def _a_ejemplo(oracion, codigo_idioma):
        transcripciones = oracion.get("transcriptions") or []

        # La app usa chino simplificado: si la oración viene en tradicional,
        # Tatoeba trae la versión simplificada como transcripción.
        texto = oracion["text"]
        if oracion.get("script") != "Hans":
            simplificado = next((t for t in transcripciones if t.get("script") == "Hans"), None)
            if simplificado:
                texto = simplificado["text"]

        # El pinyin con tildes viene en `html` (con entidades: "Xu&eacute;");
        # `text` lo trae con números ("Xue2").
        pinyin = None
        latino = next((t for t in transcripciones if t.get("script") == "Latn"), None)
        if latino:
            pinyin = html.unescape(_ETIQUETAS.sub("", latino.get("html") or latino["text"]))

        # Se prefieren las traducciones directas de la oración a las indirectas.
        traducciones = [
            t for t in oracion.get("translations") or [] if t.get("lang") == codigo_idioma
        ]
        traducciones.sort(key=lambda t: not t.get("is_direct"))
        traduccion = traducciones[0]["text"] if traducciones else None

        return Ejemplo(texto=texto, pinyin=pinyin, traduccion=traduccion)
