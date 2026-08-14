"""Servicio de apoyo: notificar al usuario que su sesión está lista."""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class Notificador(ABC):
    @abstractmethod
    def sesion_lista(self, usuario_id, sesion) -> None:
        ...


class NotificadorConsola(Notificador):
    """Desarrollo: solo imprime. Cero dependencias externas, cero costo."""

    def sesion_lista(self, usuario_id, sesion) -> None:
        logger.info(
            "[MOCK] Sesión %s lista para %s — HSK%s, %s ejercicios",
            sesion.pk,
            usuario_id,
            sesion.nivel_hsk,
            sesion.total_ejercicios(),
        )


class NotificadorEmail(Notificador):
    """Producción: envía correo real vía el backend de email de Django."""

    def __init__(self, remitente):
        self._remitente = remitente

    def sesion_lista(self, usuario_id, sesion) -> None:
        from django.core.mail import send_mail

        send_mail(
            subject="Tu sesión de práctica está lista",
            message=(
                f"Preparamos {sesion.total_ejercicios()} ejercicios de nivel "
                f"HSK{sesion.nivel_hsk}. Duración estimada: "
                f"{sesion.duracion_estimada_min} minutos."
            ),
            from_email=self._remitente,
            recipient_list=[self._resolver_email(usuario_id)],
            fail_silently=False,
        )

    def _resolver_email(self, usuario_id):
        # En producción consulta al servicio de usuarios.
        return f"{usuario_id}@example.com"
