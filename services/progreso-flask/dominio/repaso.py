"""
Repaso espaciado: utilidades que quedan del port de
services/agente-tutor/tutor/domain/repaso.py.

Desde RF-IA-02 las fechas de repaso las calcula la curva de olvido
(dominio/curva_olvido.py, SM-2 con factor de facilidad) al cerrar cada
sesión. Se retiraron calcular_proximo_repaso(), el agendado por respuesta
con intervalos fijos, y esta_pendiente(), que no se usaba: los repasos
vencidos los lista dominio/progreso.listar_repasos(). Queda INTERVALOS_DIAS porque la curva lo usa para el
estado inicial de un carácter que ya se había agendado con ese algoritmo.
"""

from datetime import datetime, timezone

# Días de espera que daba el algoritmo anterior según los aciertos seguidos.
# Índice 0 = primer acierto, índice 1 = segundo, y así.
INTERVALOS_DIAS = [1, 3, 7, 16, 35, 90]


def ahora():
    return datetime.now(timezone.utc)


def actualizar_tasa_acierto(tasa_actual, acerto, peso=0.1):
    """
    Media móvil exponencial: las respuestas recientes pesan más que las viejas.

    Con peso=0.1, una racha de 10 aciertos mueve la tasa de 0.5 a ~0.65,
    y no hace falta guardar el historial completo para calcularla.
    """
    objetivo = 1.0 if acerto else 0.0
    nueva = tasa_actual + peso * (objetivo - tasa_actual)
    return round(max(0.0, min(1.0, nueva)), 4)
