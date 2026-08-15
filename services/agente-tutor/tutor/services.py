"""
Capa de Aplicación — aquí vive el algoritmo de negocio.

La vista no sabe nada de builders, motores ni notificadores: solo llama
a este servicio. Y este servicio no sabe qué implementación concreta
recibió: las Factories lo resolvieron por él.
"""

from .domain.builders import SesionEstudioBuilder
from .infra.factories import MotorTutorFactory, NotificadorFactory
from .repositories import ProgresoRepository

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
