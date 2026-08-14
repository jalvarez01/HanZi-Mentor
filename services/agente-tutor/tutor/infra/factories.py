"""
Patrón Factory — decide QUÉ implementación concreta se instancia,
según variables de entorno. El resto del código nunca hace `if entorno == ...`.

Variables relevantes (.env):
    TUTOR_ENGINE   = MOCK | REAL      (por defecto MOCK)
    NOTIFICADOR    = CONSOLE | EMAIL  (por defecto CONSOLE)
"""

import os

from .motores import MotorTutor, MotorTutorLangGraph, MotorTutorMock
from .notificadores import Notificador, NotificadorConsola, NotificadorEmail


class MotorTutorFactory:
    """Devuelve el motor de tutoría configurado para el entorno actual."""

    @staticmethod
    def crear() -> MotorTutor:
        modo = os.getenv("TUTOR_ENGINE", "MOCK").upper()

        if modo == "REAL":
            from ..agent.graph import construir_agente

            return MotorTutorLangGraph(agente=construir_agente())

        return MotorTutorMock()


class NotificadorFactory:
    """Devuelve el notificador configurado para el entorno actual."""

    @staticmethod
    def crear() -> Notificador:
        modo = os.getenv("NOTIFICADOR", "CONSOLE").upper()

        if modo == "EMAIL":
            remitente = os.getenv("EMAIL_REMITENTE", "no-reply@hanzimentor.app")
            return NotificadorEmail(remitente=remitente)

        return NotificadorConsola()
