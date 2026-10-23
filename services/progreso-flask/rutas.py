"""Rutas HTTP: validan la entrada, delegan en el servicio y responden."""

from flask import Blueprint, jsonify, request

import serializacion
import servicio
from db import obtener_sesion
from validacion import validar_limite, validar_respuesta, validar_usuario_id

progreso_bp = Blueprint("progreso", __name__)


@progreso_bp.get("/api/v2/progreso/<usuario_id>/")
def consultar(usuario_id):
    """Estado acumulado del estudiante. Un usuario nuevo recibe los valores iniciales."""
    usuario_id = validar_usuario_id(usuario_id)
    datos = servicio.consultar_progreso(obtener_sesion(), usuario_id)
    return jsonify(serializacion.progreso(datos)), 200


@progreso_bp.post("/api/v2/progreso/<usuario_id>/respuestas/")
def registrar_respuesta(usuario_id):
    """Uso interno (flask_sesiones): registra un acierto o un error."""
    usuario_id = validar_usuario_id(usuario_id)
    caracter, acerto = validar_respuesta(request.get_json(silent=True))
    datos = servicio.registrar_respuesta(obtener_sesion(), usuario_id, caracter, acerto)
    return jsonify(serializacion.progreso(datos)), 200


@progreso_bp.get("/api/v2/progreso/<usuario_id>/refuerzos/")
def refuerzos(usuario_id):
    """Los caracteres con más fallos, de peor a mejor."""
    usuario_id = validar_usuario_id(usuario_id)
    limite = validar_limite(request.args)
    caracteres = servicio.caracteres_a_reforzar(obtener_sesion(), usuario_id, limite)
    return jsonify({"usuario_id": str(usuario_id), "caracteres": caracteres}), 200
