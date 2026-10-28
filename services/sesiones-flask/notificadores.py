"""Avisar que la sesión está lista. Port de agente-tutor/tutor/infra/notificadores.py.

Adaptadores:

- `NotificadorConsola`: solo deja una línea en el log (desarrollo).
- `NotificadorCola`: publica la tarea `notificar_sesion_lista` en Redis
  para el worker de reportes-flask (T19).

El de email usaba el backend de correo de Django y no se portó.
"""

import logging
import os
import queue
import threading
from abc import ABC, abstractmethod

from celery import Celery

from dominio import sesion as reglas

logger = logging.getLogger(__name__)

TAREA_SESION_LISTA = "notificar_sesion_lista"

# Notificaciones que esperan al hilo de publicación; las demás se descartan.
MAXIMO_PENDIENTES = 100


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


def crear_publicador(redis_url, timeout=1.0):
    """App Celery solo para publicar, igual que crear_publicador de reportes-flask.

    - Sin backend de resultados: con el de Redis, cada publicación abre una
      suscripción pub/sub al resultado que nadie espera y, con Redis caído,
      reintenta unos 40 s antes de fallar.
    - Sin reintentos de publicación y con timeouts de `timeout` segundos: con
      Redis caído, publicar falla en 1 o 2 s.
    - set_as_current=False: no reemplaza la app Celery "actual" del proceso.
    """
    publicador = Celery("sesiones-publicador", broker=redis_url, set_as_current=False)
    publicador.conf.update(
        task_serializer="json",
        accept_content=["json"],
        task_publish_retry=False,
        broker_connection_timeout=timeout,
        broker_connection_retry_on_startup=False,
        broker_transport_options={
            "socket_connect_timeout": timeout,
            "socket_timeout": timeout,
        },
    )
    return publicador


class NotificadorCola(Notificador):
    """Publica `notificar_sesion_lista` por NOMBRE: no importa código de
    reportes-flask. La ejecuta su worker de Celery.

    La notificación es de mejor esfuerzo: si Redis no responde, si la cola
    está llena o si el proceso se reinicia con trabajos pendientes, se
    pierde con un aviso en el log y la sesión se crea igual.

    Se publica en un hilo aparte y la respuesta no lo espera: con el
    contenedor de Redis detenido, solo resolver el nombre `redis` tarda
    varios segundos, y los timeouts de conexión no cubren el DNS.

    - Un solo hilo por proceso: el productor de kombu, que no es seguro entre
      hilos, se usa siempre desde el mismo.
    - Daemon: no retiene el cierre del proceso.
    - Perezoso: la cola y el hilo se crean en la primera sesión de cada
      proceso, nunca al importar ni en el maestro de gunicorn. Si el pid
      cambia (un fork después de crearlos), se crean de nuevo: los hilos no
      sobreviven a un fork.
    - Cola con límite (`maximo_pendientes`, 100): si Redis está caído, cada
      intento tarda unos segundos y los pendientes no crecen sin control.
    """

    def __init__(self, publicador, maximo_pendientes=MAXIMO_PENDIENTES):
        self._publicador = publicador
        self._maximo_pendientes = maximo_pendientes
        self._candado = threading.Lock()
        self._pid = None
        self._cola = None
        self._hilo = None

    def _asegurar_hilo(self):
        pid = os.getpid()
        if self._pid == pid:
            return
        with self._candado:
            if self._pid != pid:
                self._cola = queue.Queue(maxsize=self._maximo_pendientes)
                self._hilo = threading.Thread(
                    target=self._trabajar, args=(self._cola,), name="notificador-cola", daemon=True
                )
                self._hilo.start()
                self._pid = pid

    def sesion_lista(self, usuario_id, sesion) -> None:
        # Los datos se leen acá: la sesión de SQLAlchemy es de este hilo.
        args = [str(usuario_id), sesion.id]
        try:
            self._asegurar_hilo()
            self._cola.put_nowait(args)
        except queue.Full:
            logger.warning(
                "Cola de notificaciones llena (%s pendientes): se descarta la de la sesión %s para %s",
                self._maximo_pendientes, args[1], args[0],
            )
        except Exception as error:  # noqa: BLE001 - p. ej. no se pudo crear el hilo
            self._avisar(args, error)

    def _trabajar(self, cola):
        while True:
            args = cola.get()
            try:
                self._publicar(args)
            finally:
                cola.task_done()

    def esperar_pendientes(self):
        """Bloquea hasta publicar (o descartar) lo encolado. Para las pruebas."""
        if self._cola is not None:
            self._cola.join()

    def _publicar(self, args):
        try:
            # ignore_result viaja en el mensaje y manda sobre el de la tarea:
            # sin él, el worker guardaría 24 h un resultado vacío por sesión.
            self._publicador.send_task(TAREA_SESION_LISTA, args=args, ignore_result=True)
        except Exception as error:  # noqa: BLE001 - nunca romper la creación de la sesión
            self._avisar(args, error)

    @staticmethod
    def _avisar(args, error):
        usuario_id, sesion_id = args
        logger.warning(
            "No se pudo publicar %s de la sesión %s para %s: %s",
            TAREA_SESION_LISTA, sesion_id, usuario_id, error,
        )
