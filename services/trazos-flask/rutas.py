"""Rutas HTTP: validan la forma del JSON, delegan en el servicio y responden."""

from flask import Blueprint, current_app, jsonify, request

from servicio import validar_trazo
from validacion import EntradaInvalida, validar_solicitud

trazos_bp = Blueprint("trazos", __name__)


@trazos_bp.post("/api/v2/trazos/validar/")
def validar():
    cuerpo = request.get_json(force=True, silent=True)
    if cuerpo is None:
        raise EntradaInvalida("El cuerpo no es un JSON válido")

    solicitud = validar_solicitud(cuerpo, current_app.config["MAX_PUNTOS"])
    return jsonify(validar_trazo(solicitud)), 200
