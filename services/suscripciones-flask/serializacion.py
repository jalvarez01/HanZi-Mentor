"""Convierte el estado y los pagos en JSON. Los textos se traducen acá."""

from datetime import timezone

from dominio.planes import MONEDA, PERIODO_DIAS, PLANES
from i18n import traducir


def fecha(valor):
    if valor is None:
        return None
    return valor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def plan(p):
    return {
        "codigo": p.codigo,
        "nombre": traducir(p.nombre),
        "descripcion": traducir(p.descripcion),
        "precio": p.precio,
        "moneda": MONEDA,
        "periodo_dias": PERIODO_DIAS,
        "nivel_maximo": p.nivel_maximo,
    }


def planes(nombre_pasarela):
    return {
        "planes": [plan(p) for p in PLANES.values()],
        "pasarela": nombre_pasarela,
    }


def suscripcion(usuario_id, estado):
    return {
        "usuario_id": str(usuario_id),
        "plan": estado.plan,
        "nombre_plan": traducir(PLANES[estado.plan].nombre),
        "estado": estado.estado,
        "vence_en": fecha(estado.vence_en),
        "nivel_maximo": estado.nivel_maximo,
        "acciones": list(estado.acciones),
    }


def pago(p):
    return {
        "id": p.id,
        "concepto": p.concepto,
        "estado": p.estado,
        "codigo_rechazo": p.codigo_rechazo,
        "monto": p.monto,
        "moneda": p.moneda,
        "referencia": p.referencia,
        "pasarela": p.pasarela,
        "marca": p.marca,
        "ultimos4": p.ultimos4,
        "creado_en": fecha(p.creado_en),
    }


def resultado(usuario_id, r):
    cuerpo = {"suscripcion": suscripcion(usuario_id, r.estado)}
    if r.pago is not None:
        cuerpo["pago"] = pago(r.pago)
    return cuerpo
