"""Casos de uso del progreso.

`registrar_respuesta` es la parte de progreso que en agente-tutor hacía
ResponderEjercicioService (tutor/services.py). Acá queda sola para que
flask_sesiones (T12) la llame por HTTP en vez de tocar estas tablas.
"""

from sqlalchemy.exc import IntegrityError

from dominio import progreso as reglas
from dominio.codigos import ORIGEN_SESION, ORIGEN_TRAZOS
from dominio.repaso import actualizar_tasa_acierto, ahora, calcular_proximo_repaso
from repositorio import ProgresoRepositorio


def consultar_progreso(sesion, usuario_id):
    return ProgresoRepositorio(sesion).obtener(usuario_id)


def caracteres_a_reforzar(sesion, usuario_id, limite=3):
    return ProgresoRepositorio(sesion).caracteres_a_reforzar(usuario_id, limite)


def detectar_patrones(sesion, usuario_id, momento=None):
    """Patrones de error del usuario (RF-IA-01). Sin progreso, lista vacía."""
    progreso = ProgresoRepositorio(sesion).obtener_entidad(usuario_id)
    if progreso is None:
        return []
    return progreso.detectar_patron_error(momento or ahora())


def _con_reintento(sesion, aplicar):
    try:
        return aplicar()
    except IntegrityError:
        # Dos primeras respuestas simultáneas del mismo usuario: la otra
        # petición creó el registro antes. Se reintenta sobre ese registro.
        sesion.rollback()
        return aplicar()


def _aplicar_respuesta(sesion, usuario_id, caracter, acerto, momento, codigo_error):
    repo = ProgresoRepositorio(sesion)
    progreso = repo.obtener_o_crear_entidad(usuario_id)
    racha_previa = reglas.racha_de(progreso, caracter)

    if not acerto:
        # Antes de registrar_respuesta, que lo saca de dominados.
        dominado = caracter in (progreso.caracteres_dominados or [])
        reglas.anotar_error(progreso, caracter, codigo_error, momento, ORIGEN_SESION, dominado)

    reglas.registrar_respuesta(progreso, caracter, acerto)
    progreso.tasa_acierto = actualizar_tasa_acierto(progreso.tasa_acierto, acerto)
    reglas.agendar_repaso(
        progreso,
        caracter,
        calcular_proximo_repaso(racha_previa, acerto, desde=momento),
    )
    repo.guardar(progreso)
    sesion.commit()


def registrar_respuesta(sesion, usuario_id, caracter, acerto, momento=None, codigo_error=None):
    """Registra un acierto o un error y devuelve el progreso actualizado.

    codigo_error (RF-IA-01): tipo de error de una respuesta fallada. Con un
    acierto se ignora.
    """
    momento = momento or ahora()
    _con_reintento(
        sesion,
        lambda: _aplicar_respuesta(sesion, usuario_id, caracter, acerto, momento, codigo_error),
    )
    return ProgresoRepositorio(sesion).obtener(usuario_id)


def _aplicar_error_de_trazo(sesion, usuario_id, caracter, codigo_error, momento):
    repo = ProgresoRepositorio(sesion)
    progreso = repo.obtener_o_crear_entidad(usuario_id)
    anotado = reglas.anotar_error(progreso, caracter, codigo_error, momento, ORIGEN_TRAZOS)
    if anotado:
        repo.guardar(progreso)
    sesion.commit()
    return anotado


def registrar_error_de_trazo(sesion, usuario_id, caracter, codigo_error, momento=None):
    """Anota el tipo de error de un trazo fallado en la página Trazos.

    Es práctica libre, fuera de una sesión: solo alimenta los patrones de
    error. No cambia la racha, los dominados, los errores frecuentes, la
    tasa de acierto ni el repaso. Devuelve False si era un reintento del
    mismo trazo y no se anotó.
    """
    momento = momento or ahora()
    return _con_reintento(
        sesion,
        lambda: _aplicar_error_de_trazo(sesion, usuario_id, caracter, codigo_error, momento),
    )
