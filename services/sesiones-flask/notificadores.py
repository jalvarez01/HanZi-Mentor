"""Avisar que la sesión está lista. Port de agente-tutor/tutor/infra/notificadores.py.

Solo se porta el adaptador de consola. El de email usaba el backend de
correo de Django y no hace falta en este servicio.
"""

import logging
from abc import ABC, abstractmethod

from dominio import sesion as reglas

logger = logging.getLogger(__name__)


class Notificador(ABC):
    @abstractmethod
    def sesion_lista(self, usuario_id, sesion) -> None:
        ...


class NotificadorConsola(Notificador):
    """Desarrollo: solo deja una línea en el log."""

    def sesion_lista(self, usuario_id, sesion) -> None:
        logger.info(
            "[MOCK] Sesión %s lista para %s: HSK%s, %s ejercicios",
            sesion.id,
            usuario_id,
            sesion.nivel_hsk,
            reglas.total_ejercicios(sesion),
        )
