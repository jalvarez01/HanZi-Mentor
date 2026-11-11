"""Ciclo de vida de una suscripción: activar, renovar y cancelar Premium.

En la base solo se guardan dos estados: `activa` y `cancelada`. `vencida` se
calcula: un Premium cuya fecha de vencimiento ya pasó vale como Free, sin
que un proceso tenga que pasar a cambiarlo.

| Estado              | Plan que rige | Acciones posibles      |
|---------------------|---------------|------------------------|
| Nunca pagó          | free          | activar                |
| Premium activa      | premium       | renovar (*), cancelar  |
| Premium cancelada   | premium       | renovar (*)            |
| Premium vencida     | free          | activar                |

(*) Solo cuando faltan VENTANA_RENOVACION_DIAS (7) días o menos para el
vencimiento. Así no se puede renovar justo después de activar o de renovar
(un doble clic no cobra dos periodos seguidos), y una suscripción cancelada
puede renovarse cuando entra en esa ventana. Cada periodo sigue siendo de
PERIODO_DIAS (30) días.

Cancelar no devuelve dinero: Premium sigue hasta `vence_en` y después vuelve
a Free. Renovar una suscripción cancelada la deja activa otra vez.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from dominio.excepciones import AccionNoPermitida
from dominio.planes import FREE, PERIODO_DIAS, PLANES, PREMIUM, VENTANA_RENOVACION_DIAS
from mensajes import N_

ACTIVA = "activa"
CANCELADA = "cancelada"
VENCIDA = "vencida"

ACTIVAR = "activar"
RENOVAR = "renovar"
CANCELAR = "cancelar"

PERIODO = timedelta(days=PERIODO_DIAS)
VENTANA_RENOVACION = timedelta(days=VENTANA_RENOVACION_DIAS)


def ahora():
    # Sin microsegundos: las fechas del JSON quedan como 2026-12-11T15:00:00Z.
    return datetime.now(timezone.utc).replace(microsecond=0)


@dataclass(frozen=True)
class Estado:
    """Lo que rige hoy para un usuario, calculado a partir de lo guardado."""

    plan: str
    estado: str
    vence_en: datetime | None
    acciones: tuple

    @property
    def nivel_maximo(self):
        return PLANES[self.plan].nivel_maximo

    @property
    def renovable_desde(self):
        """Desde cuándo se puede renovar: vence_en menos la ventana de renovación.

        Solo para un Premium vigente (activo o cancelado); para Free, vencida o
        sin suscripción, None. El frontend lo usa para decir desde qué fecha
        aparece "Renovar" cuando todavía no está en `acciones`.
        """
        if self.plan != PREMIUM or self.vence_en is None:
            return None
        return self.vence_en - VENTANA_RENOVACION


def estado_actual(guardada, momento):
    """`guardada` es la Suscripcion de la base o None si el usuario nunca pagó."""
    if guardada is None or guardada.plan != PREMIUM:
        return Estado(FREE, ACTIVA, None, (ACTIVAR,))

    if guardada.vence_en <= momento:
        return Estado(FREE, VENCIDA, guardada.vence_en, (ACTIVAR,))

    acciones = []
    if guardada.vence_en - momento <= VENTANA_RENOVACION:
        acciones.append(RENOVAR)
    if guardada.estado == ACTIVA:
        acciones.append(CANCELAR)
    return Estado(PREMIUM, guardada.estado, guardada.vence_en, tuple(acciones))


def _conflicto(mensaje, codigo, **params):
    return AccionNoPermitida(mensaje, codigo, **params)


def verificar(accion, estado):
    """Lanza 409 si la acción no se puede hacer desde el estado actual."""
    if accion in estado.acciones:
        return
    if accion == ACTIVAR:
        raise _conflicto(
            N_("Ya tenés Premium. Para extenderlo, renovalo."), "YA_ES_PREMIUM"
        )
    if estado.plan != PREMIUM:
        raise _conflicto(N_("No tenés una suscripción Premium vigente."), "SIN_PREMIUM")
    if accion == CANCELAR:
        raise _conflicto(
            N_("La suscripción ya está cancelada: Premium sigue hasta que venza."),
            "YA_CANCELADA",
        )
    raise _conflicto(
        N_("Solo se puede renovar cuando faltan %(dias)s días o menos para el vencimiento."),
        "RENOVACION_ANTICIPADA",
        dias=VENTANA_RENOVACION_DIAS,
    )


def vencimiento_al_activar(momento):
    return momento + PERIODO


def vencimiento_al_renovar(vence_en, momento):
    """El periodo nuevo se suma al que queda: renovar antes no hace perder días."""
    return max(vence_en, momento) + PERIODO
