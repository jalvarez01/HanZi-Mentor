"""Rutas HTTP: validan la entrada, delegan en el servicio y responden."""

from flask import Blueprint, jsonify, request

import serializacion
import servicio
from db import obtener_sesion
from validacion import validar_consulta_caracteres, validar_generar_leccion

catalogo_bp = Blueprint("catalogo", __name__)


@catalogo_bp.get("/api/v2/caracteres/")
def caracteres():
    """GET /api/v2/caracteres/?nivel=2&excluir=学,校&limite=4"""
    nivel, excluir, limite = validar_consulta_caracteres(request.args)
    lista = servicio.listar_caracteres(obtener_sesion(), nivel, excluir, limite)
    return jsonify({"caracteres": [serializacion.caracter_lista(c) for c in lista]}), 200


@catalogo_bp.get("/api/v2/caracteres/<hanzi>/")
def detalle_caracter(hanzi):
    """Incluye los trazos en orden, con su path SVG y su mediana."""
    caracter = servicio.obtener_caracter(obtener_sesion(), hanzi)
    return jsonify(serializacion.caracter_detalle(caracter)), 200


@catalogo_bp.post("/api/v2/lecciones/generar/")
def generar_leccion():
    usuario_id, nivel_hsk, cantidad = validar_generar_leccion(request.get_json(silent=True))
    leccion = servicio.generar_leccion(obtener_sesion(), usuario_id, nivel_hsk, cantidad)
    return jsonify(serializacion.leccion(leccion)), 201


@catalogo_bp.get("/api/v2/lecciones/<int:leccion_id>/")
def detalle_leccion(leccion_id):
    leccion = servicio.obtener_leccion(obtener_sesion(), leccion_id)
    return jsonify(serializacion.leccion(leccion)), 200
