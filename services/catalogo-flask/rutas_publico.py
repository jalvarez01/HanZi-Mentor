"""Rutas públicas para el equipo aliado (T14): el resumen y el reto de pinyin.

Van en un blueprint aparte de `rutas.py` porque tienen otro consumidor (una
aplicación de otro equipo) y otras reglas:

- Aceptan peticiones desde cualquier origen (CORS), para que el aliado pueda
  llamarlas también desde un navegador, incluido el POST con JSON del reto
  (el navegador pregunta antes con OPTIONS). No cambian nada en la base y no
  usan credenciales.
- El parámetro `lang` del contrato elige el idioma de los errores. Lo normal
  es que el aliado llame desde su backend sin Accept-Language; con `lang`
  igual recibe los errores en el idioma que pidió.
"""

from contextlib import nullcontext

from flask import Blueprint, jsonify, request
from flask_babel import force_locale

import publico
from db import obtener_sesion
from errores import ErrorDominio, respuesta_error
from i18n import IDIOMAS, traducir
from mensajes import N_
from validacion import validar_consulta_resumen, validar_respuesta_reto

PREFIJO = "/api/v2/publico/"

publico_bp = Blueprint("publico", __name__)


@publico_bp.get(PREFIJO + "resumen/")
def resumen():
    """GET /api/v2/publico/resumen/?lang=en&nivel=2"""
    # `lang` no cambia la respuesta: no tiene textos para traducir (las
    # definiciones solo existen en inglés en el dataset). Se valida y elige
    # el idioma de los errores (ver error_en_el_idioma_pedido).
    _idioma, nivel = validar_consulta_resumen(request.args)
    return jsonify(publico.resumen(obtener_sesion(), nivel)), 200


@publico_bp.get(PREFIJO + "reto/")
def reto():
    """GET /api/v2/publico/reto/?lang=en&nivel=1

    Un carácter con 4 opciones de pinyin y la pregunta en el idioma de
    `lang` (o de Accept-Language). Cada llamada da un reto distinto.
    """
    idioma, nivel = validar_consulta_resumen(request.args)
    datos = publico.reto(obtener_sesion(), nivel)
    if datos is None:
        raise ErrorDominio(N_("No hay caracteres para ese nivel."), "NO_ENCONTRADO", estado=404)
    with _idioma(idioma):
        datos["pregunta"] = traducir(datos["pregunta"], {"hanzi": datos["hanzi"]})
    return jsonify(datos), 200


@publico_bp.post(PREFIJO + "reto/responder/")
def responder_reto():
    """POST /api/v2/publico/reto/responder/ con {"hanzi": "人", "respuesta": "rén"}."""
    validar_consulta_resumen(request.args)
    hanzi, respuesta = validar_respuesta_reto(request.get_json(silent=True))
    return jsonify(publico.verificar_reto(obtener_sesion(), hanzi, respuesta)), 200


def _idioma(idioma):
    """force_locale con `lang`; sin él, manda Accept-Language."""
    return force_locale(idioma) if idioma else nullcontext()


@publico_bp.errorhandler(ErrorDominio)
def error_en_el_idioma_pedido(exc):
    """Con `lang` válido, el error sale en ese idioma aunque la petición traiga
    otro Accept-Language. Sin `lang`, o con uno no soportado, manda
    Accept-Language, como en el resto del servicio."""
    idioma = request.args.get("lang")
    if idioma in IDIOMAS:
        with force_locale(idioma):
            mensaje = traducir(exc.plantilla, exc.params)
    else:
        mensaje = traducir(exc.plantilla, exc.params)
    return respuesta_error(mensaje, exc.codigo, exc.estado)


@publico_bp.after_app_request
def permitir_cualquier_origen(respuesta):
    # after_app_request y no after_request: un 404 o un 405 bajo este prefijo
    # no quedan asociados al blueprint (Flask no encuentra la ruta o el
    # método), y también tienen que llevar CORS. Las demás rutas, no.
    if request.path.startswith(PREFIJO):
        respuesta.headers["Access-Control-Allow-Origin"] = "*"
        # Para la petición previa (OPTIONS) del POST con JSON del reto.
        respuesta.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        respuesta.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept-Language"
    return respuesta
