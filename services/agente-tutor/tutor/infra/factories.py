"""
Patrón Factory — decide QUÉ implementación concreta se instancia,
según variables de entorno. El resto del código nunca hace `if entorno == ...`.

Variables relevantes (.env):
    TUTOR_ENGINE    = MOCK | REAL       (por defecto MOCK)
    NOTIFICADOR     = CONSOLE | EMAIL   (por defecto CONSOLE)
    CATALOGO        = LOCAL | REMOTO    (por defecto LOCAL)
    CATALOGO_URL    = http://localhost:5000   (catalogo-flask: listado y detalle)
    CONTENIDO_URL   = http://localhost:8002   (contenido: validación de trazos)
"""

import os

from .catalogo import Catalogo, CatalogoLocal, CatalogoRemoto
from .motores import MotorTutor, MotorTutorLangGraph, MotorTutorMock
from .notificadores import Notificador, NotificadorConsola, NotificadorEmail


class CatalogoFactory:
    """Devuelve la fuente de caracteres configurada para el entorno actual."""

    @staticmethod
    def crear() -> Catalogo:
        modo = os.getenv("CATALOGO", "LOCAL").upper()

        if modo == "REMOTO":
            return CatalogoRemoto(
                base_url=os.getenv("CATALOGO_URL", "http://localhost:5000"),
                contenido_url=os.getenv("CONTENIDO_URL", "http://localhost:8002"),
                respaldo=CatalogoLocal(),
            )

        return CatalogoLocal()


class MotorTutorFactory:
    """Devuelve el motor de tutoría configurado para el entorno actual."""

    @staticmethod
    def crear() -> MotorTutor:
        modo = os.getenv("TUTOR_ENGINE", "MOCK").upper()
        catalogo = CatalogoFactory.crear()

        if modo == "REAL":
            from ..agent.graph import construir_agente

            return MotorTutorLangGraph(agente=construir_agente(), catalogo=catalogo)

        return MotorTutorMock(catalogo=catalogo)


class NotificadorFactory:
    """Devuelve el notificador configurado para el entorno actual."""

    @staticmethod
    def crear() -> Notificador:
        modo = os.getenv("NOTIFICADOR", "CONSOLE").upper()

        if modo == "EMAIL":
            remitente = os.getenv("EMAIL_REMITENTE", "no-reply@hanzimentor.app")
            return NotificadorEmail(remitente=remitente)

        return NotificadorConsola()
