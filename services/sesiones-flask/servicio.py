"""
Casos de uso: crear una sesión adaptativa y responder un ejercicio.

Port de SesionEstudioService y ResponderEjercicioService de
agente-tutor/tutor/services.py. La diferencia es que el progreso ya no es
una tabla local: se lee y se registra en progreso-flask por HTTP
(clientes.ProgresoRemoto), y los caracteres nuevos vienen de catalogo-flask.
"""

from dominio import sesion as reglas
from dominio.builder import SesionEstudioBuilder
from dominio.excepciones import (
    EjercicioNoEncontradoError,
    EjercicioYaRespondidoError,
    SesionNoEncontradaError,
)
from dominio.repaso import calcular_proximo_repaso, racha_previa
from mensajes import N_
from modelos import ahora
from repositorio import SesionesRepositorio

CANTIDAD_REFUERZOS = 3
CANTIDAD_NUEVOS = 4

# En español; serializacion.py lo traduce al idioma de la petición.
AVISO_PROGRESO = N_(
    "La respuesta quedó guardada en la sesión, pero no se pudo actualizar "
    "el progreso: el servicio de progreso no respondió."
)


class SesionEstudioService:
    """Orquesta la creación de una sesión de estudio adaptativa."""

    def __init__(self, motor, notificador, progreso):
        # Inyección de dependencias: en tests se pasan dobles;
        # en runtime las arma fabricas.py.
        self._motor = motor
        self._notificador = notificador
        self._progreso = progreso

    def crear_sesion_adaptativa(self, sesion_db, usuario_id, nivel_hsk, duracion_min=10):
        progreso = self._progreso.obtener(usuario_id)

        dificultad = self._motor.sugerir_dificultad(progreso)
        refuerzos = self._progreso.caracteres_a_reforzar(
            usuario_id, limite=CANTIDAD_REFUERZOS
        )
        nuevos = self._motor.seleccionar_caracteres_nuevos(
            progreso, cantidad=CANTIDAD_NUEVOS
        )

        sesion = (
            SesionEstudioBuilder()
            .para_usuario(usuario_id, progreso.get("nivel_max_desbloqueado", 1))
            .en_nivel(nivel_hsk)
            .con_dificultad(dificultad)
            .con_duracion(duracion_min)
            .agregar_refuerzos(refuerzos)
            .agregar_contenido_nuevo(nuevos)
            .build(SesionesRepositorio(sesion_db))
        )

        self._notificador.sesion_lista(usuario_id, sesion)
        return sesion


class ResponderEjercicioService:
    """Registra la respuesta a un ejercicio y la informa a progreso-flask."""

    def __init__(self, progreso, reloj=ahora):
        self._progreso = progreso
        self._reloj = reloj

    def responder(self, sesion_db, ejercicio_id, acerto):
        repo = SesionesRepositorio(sesion_db)
        ejercicio = repo.obtener_ejercicio_para_responder(ejercicio_id)
        if ejercicio is None:
            raise EjercicioNoEncontradoError(N_("Ejercicio no encontrado."))
        if ejercicio.respondido:
            raise EjercicioYaRespondidoError(
                N_("El ejercicio %(id)s ya fue respondido."), id=ejercicio_id
            )

        momento = self._reloj()
        ejercicio.respondido = True
        ejercicio.fue_correcto = acerto
        ejercicio.respondido_en = momento

        sesion = ejercicio.sesion
        sesion_cerrada = reglas.cerrar_si_completa(sesion)
        pendientes = reglas.ejercicios_pendientes(sesion)
        usuario_id, caracter = sesion.usuario_id, ejercicio.caracter

        # La respuesta se guarda antes de avisar a progreso: si progreso no
        # responde, el ejercicio igual queda respondido en la sesión.
        try:
            sesion_db.commit()
        except Exception:
            sesion_db.rollback()
            raise

        resultado = {
            "ejercicio": ejercicio,
            "sesion_completada": sesion_cerrada,
            "pendientes": pendientes,
            "proximo_repaso": None,
            "tasa_acierto": None,
        }

        progreso = self._progreso.registrar_respuesta(usuario_id, caracter, acerto)
        if progreso is None:
            resultado["aviso"] = AVISO_PROGRESO
            return resultado

        # Como en v1: la fecha de repaso de ESTE carácter, en ISO con +00:00.
        racha = racha_previa(
            (progreso.get("aciertos_consecutivos") or {}).get(caracter, 0), acerto
        )
        resultado["proximo_repaso"] = calcular_proximo_repaso(racha, acerto, momento).isoformat()
        resultado["tasa_acierto"] = progreso.get("tasa_acierto")
        return resultado


def obtener_sesion(sesion_db, sesion_id):
    sesion = SesionesRepositorio(sesion_db).obtener_sesion(sesion_id)
    if sesion is None:
        raise SesionNoEncontradaError(N_("Sesión no encontrada."))
    return sesion
