"""Casos de uso: consultar, activar, renovar y cancelar Premium (RF-USR-01).

Cada operación lee la suscripción, verifica con dominio/suscripcion.py que
la acción se pueda hacer, cobra con la pasarela que recibe (si hace falta) y
guarda el resultado.

Orden al cobrar: primero la pasarela y después la base. Si la pasarela
rechaza, queda el pago rechazado en el historial y no cambia la
suscripción. Si no responde, no se guarda nada: no se sabe si cobró.
"""

from dataclasses import dataclass

from sqlalchemy import select

from dominio import suscripcion as reglas
from dominio.excepciones import PagoRechazado
from dominio.planes import MONEDA, PLANES, PREMIUM
from modelos import Pago, Suscripcion
from pasarelas.base import Cobro

ACTIVACION = "activacion"
RENOVACION = "renovacion"
LIMITE_PAGOS = 20


@dataclass(frozen=True)
class Resultado:
    estado: reglas.Estado
    pago: Pago | None = None


def _guardada(sesion, usuario_id, bloquear=False):
    consulta = select(Suscripcion).where(Suscripcion.usuario_id == usuario_id)
    if bloquear:
        # En PostgreSQL bloquea la fila hasta el commit: dos renovaciones a la
        # vez no cobran las dos. SQLite lo ignora.
        consulta = consulta.with_for_update()
    return sesion.scalars(consulta).first()


def consultar(sesion, usuario_id, momento):
    return reglas.estado_actual(_guardada(sesion, usuario_id), momento)


def _cobrar(sesion, pasarela, usuario_id, tarjeta, concepto, guardada, momento):
    """Cobra el periodo Premium y devuelve el Pago aprobado, todavía sin commit."""
    monto = PLANES[PREMIUM].precio
    datos = dict(
        usuario_id=usuario_id,
        suscripcion_id=guardada.id if guardada else None,
        concepto=concepto,
        monto=monto,
        moneda=MONEDA,
        pasarela=pasarela.nombre,
        marca=tarjeta.marca,
        ultimos4=tarjeta.ultimos4,
        creado_en=momento,
    )
    cobro = Cobro(str(usuario_id), monto, MONEDA, concepto, tarjeta)
    try:
        aprobado = pasarela.cobrar(cobro)
    except PagoRechazado as rechazo:
        sesion.add(Pago(estado="rechazado", codigo_rechazo=rechazo.codigo, **datos))
        sesion.commit()
        raise
    pago = Pago(estado="aprobado", referencia=aprobado.referencia, **datos)
    sesion.add(pago)
    return pago


def activar(sesion, pasarela, usuario_id, tarjeta, momento):
    guardada = _guardada(sesion, usuario_id, bloquear=True)
    reglas.verificar(reglas.ACTIVAR, reglas.estado_actual(guardada, momento))

    pago = _cobrar(sesion, pasarela, usuario_id, tarjeta, ACTIVACION, guardada, momento)
    if guardada is None:
        guardada = Suscripcion(usuario_id=usuario_id, creada_en=momento)
        sesion.add(guardada)
    guardada.plan = PREMIUM
    guardada.estado = reglas.ACTIVA
    guardada.inicio = momento
    guardada.vence_en = reglas.vencimiento_al_activar(momento)
    guardada.cancelada_en = None
    guardada.actualizada_en = momento
    sesion.flush()
    pago.suscripcion_id = guardada.id
    sesion.commit()
    return Resultado(reglas.estado_actual(guardada, momento), pago)


def renovar(sesion, pasarela, usuario_id, tarjeta, momento):
    guardada = _guardada(sesion, usuario_id, bloquear=True)
    reglas.verificar(reglas.RENOVAR, reglas.estado_actual(guardada, momento))

    pago = _cobrar(sesion, pasarela, usuario_id, tarjeta, RENOVACION, guardada, momento)
    guardada.inicio = momento
    guardada.vence_en = reglas.vencimiento_al_renovar(guardada.vence_en, momento)
    guardada.estado = reglas.ACTIVA
    guardada.cancelada_en = None
    guardada.actualizada_en = momento
    sesion.commit()
    return Resultado(reglas.estado_actual(guardada, momento), pago)


def cancelar(sesion, usuario_id, momento):
    guardada = _guardada(sesion, usuario_id, bloquear=True)
    reglas.verificar(reglas.CANCELAR, reglas.estado_actual(guardada, momento))

    guardada.estado = reglas.CANCELADA
    guardada.cancelada_en = momento
    guardada.actualizada_en = momento
    sesion.commit()
    return Resultado(reglas.estado_actual(guardada, momento))


def listar_pagos(sesion, usuario_id, limite=LIMITE_PAGOS):
    consulta = (
        select(Pago)
        .where(Pago.usuario_id == usuario_id)
        .order_by(Pago.creado_en.desc(), Pago.id.desc())
        .limit(limite)
    )
    return list(sesion.scalars(consulta))
