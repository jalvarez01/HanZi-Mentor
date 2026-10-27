"""Rutas HTTP: validan la entrada, delegan en el servicio y responden."""

from flask import Blueprint, current_app, jsonify, request, url_for

import servicio
from i18n import traducir
from validacion import validar_pedido_reporte, validar_task_id, validar_usuario_id

reportes_bp = Blueprint("reportes", __name__)


@reportes_bp.post("/api/v2/reportes/")
def encolar():
    """Encola el reporte y responde enseguida; el worker lo genera después."""
    usuario_id = validar_pedido_reporte(request.get_json(silent=True))
    task_id = servicio.encolar_reporte(current_app.extensions["publicador"], usuario_id)
    respuesta = jsonify({"task_id": task_id, "estado": "pendiente"})
    respuesta.headers["Location"] = url_for("reportes.consultar", task_id=task_id)
    return respuesta, 202


# Va antes que /<task_id>/ solo por claridad: tienen distinta cantidad de
# segmentos y no chocan.
@reportes_bp.get("/api/v2/reportes/notificaciones/<usuario_id>/")
def notificaciones(usuario_id):
    """Las últimas 20 notificaciones del usuario, de la más nueva a la más vieja."""
    usuario_id = validar_usuario_id(usuario_id)
    lista = servicio.listar_notificaciones(current_app.extensions["notificaciones"], usuario_id)
    return jsonify({"usuario_id": usuario_id, "notificaciones": lista}), 200


@reportes_bp.get("/api/v2/reportes/<task_id>/")
def consultar(task_id):
    """Estado del reporte. Un task_id desconocido también responde "pendiente"
    (limitación de Celery, ver servicio.py)."""
    datos = servicio.consultar_reporte(validar_task_id(task_id))
    if "error" in datos:
        datos["error"] = traducir(datos["error"])
    return jsonify(datos), 200
