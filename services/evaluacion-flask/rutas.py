"""Rutas HTTP: validan la entrada, delegan en el caso de uso y responden."""

from flask import Blueprint, current_app, jsonify, request

import serializacion
from servicio import EvaluacionService
from validacion import validar_evaluacion

evaluacion_bp = Blueprint("evaluacion", __name__)


@evaluacion_bp.post("/api/v2/evaluacion/")
def evaluar():
    solicitud = validar_evaluacion(request.get_json(silent=True))
    deps = current_app.extensions["dependencias"]
    resultado = EvaluacionService(deps.catalogo, deps.trazos).evaluar(solicitud)
    return jsonify(serializacion.resultado(resultado)), 200
