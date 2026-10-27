"""Rutas públicas para el equipo aliado (T14).

Van en un blueprint aparte de `rutas.py` porque tienen otro consumidor (una
aplicación de otro equipo) y otra regla de acceso: aceptan peticiones desde
cualquier origen (CORS), para que el aliado pueda llamarlas también desde un
navegador. Son de solo lectura y no usan credenciales.
"""

from flask import Blueprint, jsonify, request

import publico
from db import obtener_sesion
from validacion import validar_consulta_resumen

publico_bp = Blueprint("publico", __name__)


@publico_bp.get("/api/v2/publico/resumen/")
def resumen():
    """GET /api/v2/publico/resumen/?nivel=2"""
    nivel = validar_consulta_resumen(request.args)
    return jsonify(publico.resumen(obtener_sesion(), nivel)), 200


@publico_bp.after_request
def permitir_cualquier_origen(respuesta):
    # Solo para este blueprint; también aplica a sus respuestas de error.
    respuesta.headers["Access-Control-Allow-Origin"] = "*"
    return respuesta
