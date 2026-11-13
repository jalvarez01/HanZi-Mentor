"""Rutas HTTP: delegan en el servicio y arman el JSON."""

from flask import Blueprint, current_app, jsonify

import servicio

aliado_bp = Blueprint("aliado", __name__)

PREFIJO = "/api/v2/aliado"


def _catalogo():
    return current_app.extensions["catalogo_aliado"]


def _encabezado(respaldo):
    proveedor = _catalogo().proveedor
    return {"aliado": proveedor.sistema, "proveedor": proveedor.nombre, "respaldo": respaldo}


def _caja(caja):
    return {"id": caja.id, "nombre": caja.nombre, "precio": caja.precio, "imagen_url": caja.imagen_url}


@aliado_bp.get(f"{PREFIJO}/cajas/")
def listar():
    """Cajas activas del aliado, con cuántos ítems tiene cada una."""
    cajas, respaldo = _catalogo().cajas()
    return jsonify({
        **_encabezado(respaldo),
        "cajas": [{**_caja(c), "items": len(c.items)} for c in cajas],
    }), 200


@aliado_bp.post(f"{PREFIJO}/cajas/<int:caja_id>/abrir/")
def abrir(caja_id):
    """Sortea un ítem con las probabilidades que publica el aliado. No guarda nada."""
    caja, item, respaldo = servicio.abrir_caja(_catalogo(), caja_id)
    return jsonify({
        **_encabezado(respaldo),
        "caja": _caja(caja),
        "item": {
            "nombre": item.nombre,
            "rareza": item.rareza,
            "valor_estimado": item.valor_estimado,
            "imagen_url": item.imagen_url,
            "probabilidad": f"{item.probabilidad:.2f}",
        },
    }), 200
