"""
Repaso espaciado: decide cuándo volver a mostrar un carácter.

Port de services/agente-tutor/tutor/domain/repaso.py. El único cambio es
que `django.utils.timezone.now()` pasa a ser `datetime.now(timezone.utc)`.

Basado en SM-2 (el algoritmo de Anki), simplificado: en vez de guardar un
factor de facilidad por carácter, el intervalo sale del número de aciertos
consecutivos. Si algo se acierta seguido, el próximo repaso se aleja; si se
falla, vuelve a tocar en unas horas.
"""

from datetime import datetime, timedelta, timezone

# Días de espera según cuántas veces seguidas se acertó.
# Índice 0 = primer acierto, índice 1 = segundo, y así.
INTERVALOS_DIAS = [1, 3, 7, 16, 35, 90]

INTERVALO_TRAS_FALLO_HORAS = 12


def ahora():
    return datetime.now(timezone.utc)


def calcular_proximo_repaso(aciertos_consecutivos, acerto, desde=None):
    """
    Devuelve el datetime del próximo repaso.

    aciertos_consecutivos: cuántas veces seguidas se acertó ANTES de esta respuesta.
    acerto: si la respuesta actual fue correcta.
    desde: momento base (por defecto, ahora).
    """
    base = desde or ahora()

    if not acerto:
        return base + timedelta(hours=INTERVALO_TRAS_FALLO_HORAS)

    indice = min(aciertos_consecutivos, len(INTERVALOS_DIAS) - 1)
    return base + timedelta(days=INTERVALOS_DIAS[indice])


def esta_pendiente(proximo_repaso, momento=None):
    """True si ya toca repasar (o si nunca se agendó)."""
    if proximo_repaso is None:
        return True
    return proximo_repaso <= (momento or ahora())


def actualizar_tasa_acierto(tasa_actual, acerto, peso=0.1):
    """
    Media móvil exponencial: las respuestas recientes pesan más que las viejas.

    Con peso=0.1, una racha de 10 aciertos mueve la tasa de 0.5 a ~0.65,
    y no hace falta guardar el historial completo para calcularla.
    """
    objetivo = 1.0 if acerto else 0.0
    nueva = tasa_actual + peso * (objetivo - tasa_actual)
    return round(max(0.0, min(1.0, nueva)), 4)
