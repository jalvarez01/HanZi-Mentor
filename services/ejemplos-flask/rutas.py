"""Rutas HTTP: validan la entrada, delegan en el caso de uso y responden."""

from flask import Blueprint, current_app, jsonify, request

from i18n import traducir
from servicio import buscar_ejemplos
from validacion import validar_consulta

ejemplos_bp = Blueprint("ejemplos", __name__)


@ejemplos_bp.get("/api/v2/ejemplos/<hanzi>/")
def ejemplos(hanzi):
    hanzi, idioma, limite = validar_consulta(hanzi, request.args)
    proveedor = current_app.extensions["proveedor_ejemplos"]
    datos = buscar_ejemplos(proveedor, hanzi, idioma, limite)
    # El crédito de la licencia es texto para personas: va en el idioma de la petición.
    datos["atribucion"] = traducir(datos["atribucion"])
    return jsonify(datos), 200
