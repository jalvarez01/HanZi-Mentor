"""Rutas HTTP: validan la entrada, delegan en el servicio y responden."""

from flask import Blueprint, jsonify, request

import serializacion
import servicio
from db import obtener_sesion
from dominio.patrones import VENTANA_DIAS
from validacion import (
    LIMITE_REPASOS_DEFECTO,
    validar_curva_olvido,
    validar_dias,
    validar_error_de_trazo,
    validar_limite,
    validar_respuesta,
    validar_usuario_id,
)

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
    caracter, acerto, codigo_error = validar_respuesta(request.get_json(silent=True))
    datos = servicio.registrar_respuesta(
        obtener_sesion(), usuario_id, caracter, acerto, codigo_error=codigo_error
    )
    return jsonify(serializacion.progreso(datos)), 200


@progreso_bp.post("/api/v2/progreso/<usuario_id>/errores/")
def registrar_error_de_trazo(usuario_id):
    """Página Trazos: anota el tipo de error de un trazo fallado (RF-IA-01).

    Solo alimenta los patrones: no cambia racha, dominados, tasa ni repaso.
    `registrado` es false si era un reintento del mismo trazo.
    """
    usuario_id = validar_usuario_id(usuario_id)
    caracter, codigo_error = validar_error_de_trazo(request.get_json(silent=True))
    registrado = servicio.registrar_error_de_trazo(
        obtener_sesion(), usuario_id, caracter, codigo_error
    )
    return jsonify({"usuario_id": str(usuario_id), "registrado": registrado}), 200


@progreso_bp.get("/api/v2/progreso/<usuario_id>/patrones/")
def patrones(usuario_id):
    """Patrones de error del estudiante, del más relevante al menos relevante."""
    usuario_id = validar_usuario_id(usuario_id)
    detectados = servicio.detectar_patrones(obtener_sesion(), usuario_id)
    return jsonify({
        "usuario_id": str(usuario_id),
        "ventana_dias": VENTANA_DIAS,
        "patrones": [serializacion.patron(p) for p in detectados],
    }), 200


@progreso_bp.get("/api/v2/progreso/<usuario_id>/refuerzos/")
def refuerzos(usuario_id):
    """Los caracteres con más fallos, de peor a mejor."""
    usuario_id = validar_usuario_id(usuario_id)
    limite = validar_limite(request.args)
    caracteres = servicio.caracteres_a_reforzar(obtener_sesion(), usuario_id, limite)
    return jsonify({"usuario_id": str(usuario_id), "caracteres": caracteres}), 200


@progreso_bp.post("/api/v2/progreso/<usuario_id>/curva-olvido/")
def curva_olvido(usuario_id):
    """Uso interno (flask_sesiones): aplica la curva de olvido de una sesión
    cerrada (RF-IA-02). Idempotente: una sesión ya aplicada responde 200 con
    `aplicada` false y no cambia nada."""
    usuario_id = validar_usuario_id(usuario_id)
    sesion_id, cerrada_en, respuestas = validar_curva_olvido(request.get_json(silent=True))
    repasos_agendados = servicio.aplicar_curva_olvido(
        obtener_sesion(), usuario_id, sesion_id, cerrada_en, respuestas
    )
    return jsonify({
        "usuario_id": str(usuario_id),
        "sesion_id": sesion_id,
        "aplicada": repasos_agendados is not None,
        "repasos": [serializacion.repaso(r) for r in repasos_agendados or []],
    }), 200


@progreso_bp.get("/api/v2/progreso/<usuario_id>/repasos/")
def repasos(usuario_id):
    """Repasos vencidos y de los próximos `dias` días, cada lista hasta `limite`."""
    usuario_id = validar_usuario_id(usuario_id)
    dias = validar_dias(request.args)
    limite = validar_limite(request.args, defecto=LIMITE_REPASOS_DEFECTO)
    momento, vencidos, proximos = servicio.listar_repasos(obtener_sesion(), usuario_id, dias, limite)
    return jsonify({
        "usuario_id": str(usuario_id),
        "momento": serializacion.fecha(momento),
        "dias": dias,
        "vencidos": [serializacion.repaso(r) for r in vencidos],
        "proximos": [serializacion.repaso(r) for r in proximos],
    }), 200
