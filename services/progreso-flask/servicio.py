"""Casos de uso del progreso.

`registrar_respuesta` es la parte de progreso que en agente-tutor hacía
ResponderEjercicioService (tutor/services.py). Acá queda sola para que
flask_sesiones (T12) la llame por HTTP en vez de tocar estas tablas.
"""

from sqlalchemy.exc import IntegrityError

from dominio import progreso as reglas
from dominio.repaso import actualizar_tasa_acierto, ahora, calcular_proximo_repaso
from repositorio import ProgresoRepositorio


def consultar_progreso(sesion, usuario_id):
    return ProgresoRepositorio(sesion).obtener(usuario_id)


def caracteres_a_reforzar(sesion, usuario_id, limite=3):
    return ProgresoRepositorio(sesion).caracteres_a_reforzar(usuario_id, limite)


def _aplicar_respuesta(sesion, usuario_id, caracter, acerto, momento):
    repo = ProgresoRepositorio(sesion)
    progreso = repo.obtener_o_crear_entidad(usuario_id)
    racha_previa = reglas.racha_de(progreso, caracter)

    reglas.registrar_respuesta(progreso, caracter, acerto)
    progreso.tasa_acierto = actualizar_tasa_acierto(progreso.tasa_acierto, acerto)
    reglas.agendar_repaso(
        progreso,
        caracter,
        calcular_proximo_repaso(racha_previa, acerto, desde=momento),
    )
    repo.guardar(progreso)
    sesion.commit()


def registrar_respuesta(sesion, usuario_id, caracter, acerto, momento=None):
    """Registra un acierto o un error y devuelve el progreso actualizado."""
    momento = momento or ahora()
    try:
        _aplicar_respuesta(sesion, usuario_id, caracter, acerto, momento)
    except IntegrityError:
        # Dos primeras respuestas simultáneas del mismo usuario: la otra
        # petición creó el registro antes. Se reintenta sobre ese registro.
        sesion.rollback()
        _aplicar_respuesta(sesion, usuario_id, caracter, acerto, momento)
    return ProgresoRepositorio(sesion).obtener(usuario_id)
