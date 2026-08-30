"""
Reglas sobre el ciclo de vida de una sesión de estudio: cuándo se
considera completa. El modelo SesionEstudio solo persiste el estado;
estas funciones deciden cuándo cambia. Mismo enfoque que
domain/progreso_logic.py.
"""


def total_ejercicios(sesion):
    return sesion.ejercicios.count()


def ejercicios_pendientes(sesion):
    return sesion.ejercicios.filter(respondido=False).count()


def esta_pendiente(ejercicio):
    return not ejercicio.respondido


def cerrar_si_completa(sesion):
    """Marca la sesión como completada cuando ya no quedan pendientes."""
    if ejercicios_pendientes(sesion) == 0 and sesion.estado != "completada":
        sesion.estado = "completada"
        sesion.save(update_fields=["estado"])
        return True
    return False
