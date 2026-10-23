"""Pruebas del adaptador de Tatoeba, sin salir a internet.

Las respuestas de ejemplo son recortes de respuestas reales de
GET https://api.tatoeba.org/v1/sentences. La prueba en vivo solo corre con
TATOEBA_EN_VIVO=1.
"""

import os
import urllib.parse

import pytest

from adaptadores.fabrica import crear_proveedor
from adaptadores.tatoeba import AdaptadorTatoeba
from app import create_app
from dominio.ejemplo import Ejemplo
from dominio.puertos import ProveedorNoDisponible

SIMPLIFICADA = {
    "id": 628103,
    "text": "学吧！",
    "lang": "cmn",
    "script": "Hans",
    "transcriptions": [
        {"script": "Hant", "text": "學吧！", "type": "altscript", "html": "學吧！"},
        {"script": "Latn", "text": "Xue2 ba5!", "type": "transcription", "html": "Xu&eacute; ba!"},
    ],
    "translations": [
        {"id": 330098, "text": "Estudia.", "lang": "spa", "is_direct": False},
        {"id": 563642, "text": "Estudiad.", "lang": "spa", "is_direct": True},
    ],
}

TRADICIONAL = {
    "id": 13412514,
    "text": "微笑！學習！",
    "lang": "cmn",
    "script": "Hant",
    "transcriptions": [
        {"script": "Hans", "text": "微笑！学习！", "type": "altscript", "html": "微笑！学习！"},
        {"script": "Latn", "text": "Wei1xiao4! xue2xi2!", "type": "transcription",
         "html": "Wēixi&agrave;o! xu&eacute;x&iacute;!"},
    ],
    "translations": [{"id": 1, "text": "¡Sonríe y aprende!", "lang": "spa", "is_direct": True}],
}

SIN_TRANSCRIPCIONES = {
    "id": 5,
    "text": "我学中文。",
    "lang": "cmn",
    "script": "Hans",
    "translations": [{"id": 2, "text": "Estudio chino.", "lang": "spa", "is_direct": True}],
}


class TatoebaFalsa:
    """Reemplaza la llamada HTTP: guarda las URL pedidas y devuelve lo indicado."""

    def __init__(self, respuesta=None, error=None):
        self.respuesta = respuesta if respuesta is not None else {"data": [], "paging": {}}
        self.error = error
        self.urls = []

    def __call__(self, url, timeout):
        self.urls.append((url, timeout))
        if self.error:
            raise self.error
        return self.respuesta


def adaptador(**kwargs):
    falsa = TatoebaFalsa(**kwargs)
    return AdaptadorTatoeba("https://api.tatoeba.org/", 2.5, obtener=falsa), falsa


def parametros(url):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))


# --- Petición a Tatoeba ---

def test_pide_oraciones_en_chino_con_traduccion_al_idioma():
    tatoeba, falsa = adaptador()

    tatoeba.obtener("学", "es", 3)

    url, timeout = falsa.urls[0]
    assert url.startswith("https://api.tatoeba.org/v1/sentences?")
    assert parametros(url) == {
        "lang": "cmn",
        "q": '"学"',
        "trans:lang": "spa",
        "sort": "relevance",
        # El doble del límite, para compensar las frases repetidas.
        "limit": "6",
        "include": "transcriptions",
    }
    assert timeout == 2.5


def test_ingles_se_pide_como_eng():
    tatoeba, falsa = adaptador()

    tatoeba.obtener("学习", "en", 5)

    assert parametros(falsa.urls[0][0])["trans:lang"] == "eng"
    assert parametros(falsa.urls[0][0])["q"] == '"学习"'


# --- Traducción de la respuesta al dominio ---

def test_convierte_la_respuesta_en_ejemplos():
    tatoeba, _ = adaptador(respuesta={"data": [SIMPLIFICADA]})

    assert tatoeba.obtener("学", "es", 3) == [
        # Pinyin con tildes y la traducción directa antes que la indirecta.
        Ejemplo(texto="学吧！", pinyin="Xué ba!", traduccion="Estudiad.")
    ]


def test_usa_la_version_simplificada_de_oraciones_en_tradicional():
    tatoeba, _ = adaptador(respuesta={"data": [TRADICIONAL]})

    [ejemplo] = tatoeba.obtener("学", "es", 3)

    assert ejemplo.texto == "微笑！学习！"
    assert ejemplo.pinyin == "Wēixiào! xuéxí!"


def test_campos_faltantes_quedan_en_none():
    tatoeba, _ = adaptador(respuesta={"data": [SIN_TRANSCRIPCIONES]})

    [ejemplo] = tatoeba.obtener("学", "en", 3)

    assert ejemplo.texto == "我学中文。"
    assert ejemplo.pinyin is None
    # Solo hay traducción al español y se pidió inglés.
    assert ejemplo.traduccion is None


def test_descarta_frases_repetidas_y_respeta_el_limite():
    # Tatoeba tiene 谢谢！ en simplificado y 謝謝！ en tradicional: ambas
    # quedan como 谢谢！ y solo debe salir una.
    repetida = {**TRADICIONAL, "id": 9, "text": "謝謝！", "transcriptions": [
        {"script": "Hans", "text": "谢谢！", "html": "谢谢！"},
    ]}
    original = {**SIN_TRANSCRIPCIONES, "id": 8, "text": "谢谢！"}
    tatoeba, _ = adaptador(respuesta={"data": [original, repetida, SIMPLIFICADA, TRADICIONAL]})

    ejemplos = tatoeba.obtener("谢", "es", 2)

    assert [e.texto for e in ejemplos] == ["谢谢！", "学吧！"]


def test_sin_resultados_devuelve_lista_vacia():
    tatoeba, _ = adaptador(respuesta={"data": [], "paging": {"total": 0}})

    assert tatoeba.obtener("龘", "es", 3) == []


# --- Fallas de Tatoeba ---

def test_si_tatoeba_no_responde_lanza_proveedor_no_disponible():
    tatoeba, _ = adaptador(error=ProveedorNoDisponible("timeout"))

    with pytest.raises(ProveedorNoDisponible):
        tatoeba.obtener("学", "es", 3)


@pytest.mark.parametrize("respuesta", [{"mensaje": "otro formato"}, {"data": [{"sin": "texto"}]}, {"data": None}])
def test_respuesta_inesperada_lanza_proveedor_no_disponible(respuesta):
    tatoeba, _ = adaptador(respuesta=respuesta)

    with pytest.raises(ProveedorNoDisponible):
        tatoeba.obtener("学", "es", 3)


def test_endpoint_con_tatoeba_caido_responde_503():
    tatoeba, _ = adaptador(error=ProveedorNoDisponible("timeout"))
    cliente = create_app({"TESTING": True}, proveedor=tatoeba).test_client()

    resp = cliente.get("/api/v2/ejemplos/学/")

    assert resp.status_code == 503
    assert resp.get_json()["codigo"] == "PROVEEDOR_NO_DISPONIBLE"


def test_endpoint_con_tatoeba_incluye_la_atribucion():
    tatoeba, _ = adaptador(respuesta={"data": [SIMPLIFICADA]})
    cliente = create_app({"TESTING": True}, proveedor=tatoeba).test_client()

    datos = cliente.get("/api/v2/ejemplos/学/").get_json()

    assert datos["proveedor"] == "tatoeba"
    assert datos["atribucion"] == "Oraciones de Tatoeba.org (CC BY 2.0 FR)"
    assert datos["ejemplos"][0]["traduccion"] == "Estudiad."


# --- Fábrica ---

def test_fabrica_crea_tatoeba_con_su_configuracion():
    proveedor = crear_proveedor({
        "PROVEEDOR_EJEMPLOS": "tatoeba",
        "TATOEBA_URL": "https://api.dev.tatoeba.org",
        "TATOEBA_TIMEOUT": 1.5,
    })

    assert isinstance(proveedor, AdaptadorTatoeba)
    assert proveedor._url("学", "es", 1).startswith("https://api.dev.tatoeba.org/v1/sentences?")
    assert proveedor._timeout == 1.5


# --- Contra la API real (opcional) ---

@pytest.mark.skipif(os.environ.get("TATOEBA_EN_VIVO") != "1", reason="solo con TATOEBA_EN_VIVO=1")
def test_en_vivo_contra_tatoeba():
    tatoeba = AdaptadorTatoeba("https://api.tatoeba.org", 10)

    ejemplos = tatoeba.obtener("学", "es", 3)

    assert 1 <= len(ejemplos) <= 3
    assert all("学" in e.texto for e in ejemplos)
    assert all(e.traduccion for e in ejemplos)
