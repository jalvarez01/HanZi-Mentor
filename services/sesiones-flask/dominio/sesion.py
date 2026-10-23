"""
Reglas sobre el ciclo de vida de una sesión de estudio: cuándo se considera
completa. Port de agente-tutor/tutor/domain/sesion_logic.py.

El modelo solo persiste el estado; estas funciones deciden cuándo cambia y
nunca guardan: el commit lo hace el servicio.
"""


def total_ejercicios(sesion):
    return len(sesion.ejercicios)


def ejercicios_pendientes(sesion):
    return sum(1 for ejercicio in sesion.ejercicios if not ejercicio.respondido)


def esta_pendiente(ejercicio):
    return not ejercicio.respondido


def cerrar_si_completa(sesion):
    """Marca la sesión como completada cuando ya no quedan pendientes."""
    if ejercicios_pendientes(sesion) == 0 and sesion.estado != "completada":
        sesion.estado = "completada"
        return True
    return False
