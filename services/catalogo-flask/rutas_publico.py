"""Rutas públicas para el equipo aliado (T14).

Van en un blueprint aparte de `rutas.py` porque tienen otro consumidor (una
aplicación de otro equipo) y otras reglas:

- Aceptan peticiones desde cualquier origen (CORS), para que el aliado pueda
  llamarlas también desde un navegador. Son de solo lectura y no usan
  credenciales.
- El parámetro `lang` del contrato elige el idioma de los errores. Lo normal
  es que el aliado llame desde su backend sin Accept-Language; con `lang`
  igual recibe los errores en el idioma que pidió.
"""

from flask import Blueprint, jsonify, request
from flask_babel import force_locale

import publico
from db import obtener_sesion
from errores import ErrorDominio, respuesta_error
from i18n import IDIOMAS, traducir
from validacion import validar_consulta_resumen

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
    return respuesta
