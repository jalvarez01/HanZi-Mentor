"""Intervalos del repaso espaciado, iguales a los de progreso-flask.

Se usan solo para informar en la respuesta cuándo vuelve a tocar el carácter
(`proximo_repaso`, como en v1). La agenda real la guarda progreso-flask.
"""

from datetime import timedelta

# Días de espera según cuántas veces seguidas se acertó.
INTERVALOS_DIAS = [1, 3, 7, 16, 35, 90]

INTERVALO_TRAS_FALLO_HORAS = 12


def calcular_proximo_repaso(aciertos_consecutivos, acerto, desde):
    """aciertos_consecutivos: racha ANTES de esta respuesta."""
    if not acerto:
        return desde + timedelta(hours=INTERVALO_TRAS_FALLO_HORAS)
    indice = min(aciertos_consecutivos, len(INTERVALOS_DIAS) - 1)
    return desde + timedelta(days=INTERVALOS_DIAS[indice])


def racha_previa(aciertos_despues, acerto):
    """La racha antes de responder, a partir de la que devuelve progreso-flask.

    Un acierto suma 1 a la racha y un error la deja en 0.
    """
    return max(aciertos_despues - 1, 0) if acerto else 0
