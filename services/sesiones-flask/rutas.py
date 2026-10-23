"""Rutas HTTP: validan la entrada, delegan en los casos de uso y responden."""

from flask import Blueprint, current_app, jsonify, request

import serializacion
from db import obtener_sesion
from servicio import ResponderEjercicioService, SesionEstudioService, obtener_sesion as buscar_sesion
from validacion import validar_crear_sesion, validar_respuesta

sesiones_bp = Blueprint("sesiones", __name__)


def _dependencias():
    return current_app.extensions["dependencias"]


@sesiones_bp.post("/api/v2/sesiones/")
def crear_sesion():
    usuario_id, nivel_hsk, duracion = validar_crear_sesion(request.get_json(silent=True))
    deps = _dependencias()
    servicio = SesionEstudioService(deps.motor, deps.notificador, deps.progreso)
    sesion = servicio.crear_sesion_adaptativa(
        obtener_sesion(), usuario_id, nivel_hsk, duracion_min=duracion
    )
    return jsonify(serializacion.sesion(sesion)), 201


@sesiones_bp.get("/api/v2/sesiones/<int:sesion_id>/")
def detalle_sesion(sesion_id):
    """Permite retomar una sesión en curso."""
    return jsonify(serializacion.sesion(buscar_sesion(obtener_sesion(), sesion_id))), 200


@sesiones_bp.post("/api/v2/ejercicios/<int:ejercicio_id>/responder/")
def responder_ejercicio(ejercicio_id):
    acerto = validar_respuesta(request.get_json(silent=True))
    servicio = ResponderEjercicioService(_dependencias().progreso)
    resultado = servicio.responder(obtener_sesion(), ejercicio_id, acerto)
    return jsonify(serializacion.resultado_respuesta(resultado)), 200
