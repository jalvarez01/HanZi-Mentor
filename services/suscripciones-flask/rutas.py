"""Rutas HTTP: validan la entrada, delegan en el servicio y responden."""

from flask import Blueprint, current_app, jsonify, request

import serializacion
import servicio
from db import obtener_sesion
from validacion import validar_activacion, validar_renovacion, validar_usuario_id

suscripciones_bp = Blueprint("suscripciones", __name__)

PREFIJO = "/api/v2/suscripciones"


def _ahora():
    # Las pruebas fijan la hora con config["RELOJ"].
    return current_app.config["RELOJ"]()


def _pasarela():
    return current_app.extensions["pasarela"]


@suscripciones_bp.get(f"{PREFIJO}/planes/")
def planes():
    """Catálogo de planes con precio, periodo y niveles que desbloquean."""
    return jsonify(serializacion.planes(_pasarela().nombre)), 200


@suscripciones_bp.get(f"{PREFIJO}/<usuario_id>/")
def consultar(usuario_id):
    """Plan que rige hoy. Un usuario que nunca pagó recibe Free."""
    usuario_id = validar_usuario_id(usuario_id)
    estado = servicio.consultar(obtener_sesion(), usuario_id, _ahora())
    return jsonify(serializacion.suscripcion(usuario_id, estado)), 200


@suscripciones_bp.post(f"{PREFIJO}/<usuario_id>/activar/")
def activar(usuario_id):
    """Cobra el primer periodo y activa Premium por 30 días."""
    usuario_id = validar_usuario_id(usuario_id)
    momento = _ahora()
    tarjeta = validar_activacion(request.get_json(silent=True), momento)
    r = servicio.activar(obtener_sesion(), _pasarela(), usuario_id, tarjeta, momento)
    return jsonify(serializacion.resultado(usuario_id, r)), 201


@suscripciones_bp.post(f"{PREFIJO}/<usuario_id>/renovar/")
def renovar(usuario_id):
    """Cobra otro periodo y lo suma al que queda. Anula una cancelación."""
    usuario_id = validar_usuario_id(usuario_id)
    momento = _ahora()
    tarjeta = validar_renovacion(request.get_json(silent=True), momento)
    r = servicio.renovar(obtener_sesion(), _pasarela(), usuario_id, tarjeta, momento)
    return jsonify(serializacion.resultado(usuario_id, r)), 200


@suscripciones_bp.post(f"{PREFIJO}/<usuario_id>/cancelar/")
def cancelar(usuario_id):
    """Sin reembolso: Premium sigue hasta `vence_en` y después vuelve a Free."""
    usuario_id = validar_usuario_id(usuario_id)
    r = servicio.cancelar(obtener_sesion(), usuario_id, _ahora())
    return jsonify(serializacion.resultado(usuario_id, r)), 200


@suscripciones_bp.get(f"{PREFIJO}/<usuario_id>/pagos/")
def pagos(usuario_id):
    """Historial de cobros, del más reciente al más antiguo (hasta 20)."""
    usuario_id = validar_usuario_id(usuario_id)
    lista = servicio.listar_pagos(obtener_sesion(), usuario_id)
    return jsonify({
        "usuario_id": str(usuario_id),
        "pagos": [serializacion.pago(p) for p in lista],
    }), 200
