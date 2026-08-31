"""
Capa de Aplicación — aquí vive el algoritmo de negocio.

La vista no sabe nada de builders, motores ni notificadores: solo llama
a estos servicios. Y los servicios no saben qué implementación concreta
recibieron: las Factories lo resolvieron por ellos.
"""

from django.db import transaction
from django.utils import timezone

from .domain import progreso_logic, sesion_logic
from .domain.builders import SesionEstudioBuilder
from .domain.exceptions import EjercicioYaRespondidoError
from .domain.repaso import actualizar_tasa_acierto, calcular_proximo_repaso
from .infra.factories import MotorTutorFactory, NotificadorFactory
from .models import Ejercicio
from progreso.repositories import ProgresoRepository

CANTIDAD_REFUERZOS = 3
CANTIDAD_NUEVOS = 4


class SesionEstudioService:
    """Orquesta la creación de una sesión de estudio adaptativa."""

    def __init__(self, motor=None, notificador=None, progreso_repo=None):
        # Inyección de dependencias: en tests se pasan dobles;
        # en runtime las Factories deciden la implementación.
        self._motor = motor or MotorTutorFactory.crear()
        self._notificador = notificador or NotificadorFactory.crear()
        self._progreso = progreso_repo or ProgresoRepository()

    def crear_sesion_adaptativa(self, usuario_id, nivel_hsk, duracion_min=10):
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
            .para_usuario(usuario_id, progreso["nivel_max_desbloqueado"])
            .en_nivel(nivel_hsk)
            .con_dificultad(dificultad)
            .con_duracion(duracion_min)
            .agregar_refuerzos(refuerzos)
            .agregar_contenido_nuevo(nuevos)
            .build()
        )

        self._notificador.sesion_lista(usuario_id, sesion)
        return sesion


class ResponderEjercicioService:
    """Registra la respuesta a un ejercicio y actualiza el progreso del usuario."""

    def __init__(self, progreso_repo=None, reloj=None):
        self._progreso = progreso_repo or ProgresoRepository()
        self._reloj = reloj or timezone.now

    @transaction.atomic
    def responder(self, ejercicio_id, acerto):
        ejercicio = Ejercicio.objects.select_related("sesion").get(pk=ejercicio_id)

        if ejercicio.respondido:
            raise EjercicioYaRespondidoError(
                f"El ejercicio {ejercicio_id} ya fue respondido."
            )

        ahora = self._reloj()
        usuario_id = ejercicio.sesion.usuario_id
        caracter = ejercicio.caracter

        progreso = self._progreso.obtener_o_crear_entidad(usuario_id)
        racha_previa = progreso_logic.racha_de(progreso, caracter)

        progreso_logic.registrar_respuesta(progreso, caracter, acerto)

        progreso.tasa_acierto = actualizar_tasa_acierto(progreso.tasa_acierto, acerto)
        progreso_logic.agendar_repaso(
            progreso,
            caracter,
            calcular_proximo_repaso(racha_previa, acerto, desde=ahora),
        )
        self._progreso.guardar(progreso)

        ejercicio.respondido = True
        ejercicio.fue_correcto = acerto
        ejercicio.respondido_en = ahora
        ejercicio.save(update_fields=["respondido", "fue_correcto", "respondido_en"])

        sesion_cerrada = sesion_logic.cerrar_si_completa(ejercicio.sesion)

        return {
            "ejercicio": ejercicio,
            "sesion_completada": sesion_cerrada,
            "pendientes": sesion_logic.ejercicios_pendientes(ejercicio.sesion),
            "proximo_repaso": progreso.agenda_repaso.get(caracter),
            "tasa_acierto": progreso.tasa_acierto,
        }
