"""Fixtures comunes: app y tareas sin Redis, worker ni red.

- Celery corre en modo eager (la tarea se ejecuta en el mismo proceso) y
  guarda los resultados en un backend en memoria (`cache+memory://`). Los
  resultados pasan igual por JSON, como en Redis.
- `PublicadorEager` reemplaza a la app Celery que encola por nombre.
- progreso y las notificaciones son dobles en memoria, inyectados en
  `tareas.dependencias` y en create_app.
"""

import pytest
import redis

import tareas
from app import create_app
from clientes import ServicioNoDisponible
from fabricas import Dependencias
from i18n import compilar_traducciones
from notificaciones import NotificacionesEnMemoria

USUARIO = "6f1c2a9e-3b7d-4c11-9f0a-2d5e8b7c4a10"

PROGRESO = {
    "usuario_id": USUARIO,
    "nivel_hsk": 2,
    "nivel_max_desbloqueado": 2,
    "tasa_acierto": 0.75,
    "caracteres_dominados": ["人", "口"],
    "errores_frecuentes": {"学": 3, "水": 1},
    "aciertos_consecutivos": {"人": 3, "口": 3},
    "proximo_repaso": "2026-10-27T15:00:00Z",
    "actualizado_en": "2026-10-26T15:00:00Z",
    "total_dominados": 2,
    "total_por_reforzar": 2,
    "caracteres_debiles": [{"caracter": "学", "fallos": 3}, {"caracter": "水", "fallos": 1}],
}


class RedisFalso:
    def __init__(self, caido=False):
        self.caido = caido

    def ping(self):
        if self.caido:
            raise redis.ConnectionError("Redis caído")
        return True


class ProgresoFalso:
    def __init__(self, datos=None, caido=False, estado=None):
        self.datos = PROGRESO if datos is None else datos
        self.caido = caido
        self.estado = estado
        self.consultas = []

    def obtener(self, usuario_id):
        self.consultas.append(usuario_id)
        if self.caido:
            raise ServicioNoDisponible("progreso caído", self.estado)
        return dict(self.datos)


class PublicadorEager:
    """Como `send_task` por nombre, pero ejecuta la tarea en el proceso."""

    def __init__(self):
        self.enviadas = []

    def send_task(self, nombre, args=None, **opciones):
        self.enviadas.append((nombre, args))
        return tareas.celery_app.tasks[nombre].apply_async(args=args)


# Se configura al importar, antes de que se registren las tareas: Celery
# copia task_store_eager_result en cada tarea al registrarla.
tareas.celery_app.conf.update(
    task_always_eager=True,
    task_store_eager_result=True,
    result_backend="cache+memory://",
)


def _olvidar_backend():
    # El backend se crea una vez y queda guardado: se fuerza a recrearlo.
    if hasattr(tareas.celery_app._local, "backend"):
        del tareas.celery_app._local.backend


@pytest.fixture(autouse=True)
def backend_nuevo():
    _olvidar_backend()
    yield
    _olvidar_backend()


@pytest.fixture
def progreso():
    return ProgresoFalso()


@pytest.fixture
def notificaciones():
    return NotificacionesEnMemoria()


@pytest.fixture(autouse=True)
def dependencias(monkeypatch, progreso, notificaciones):
    deps = Dependencias(progreso=progreso, notificaciones=notificaciones)
    monkeypatch.setattr(tareas, "dependencias", deps)
    return deps


@pytest.fixture
def redis_falso():
    return RedisFalso()


@pytest.fixture
def publicador():
    return PublicadorEager()


@pytest.fixture
def app(redis_falso, notificaciones, publicador):
    return create_app(
        {"TESTING": True, "SERVICE_NAME": "servicio-prueba"},
        redis_cliente=redis_falso,
        notificaciones=notificaciones,
        publicador=publicador,
    )


@pytest.fixture
def client(app):
    return app.test_client()


def pytest_configure(config):
    # Las pruebas de idioma necesitan los .mo. No se suben al repo: en Docker
    # los genera `pybabel compile` y acá se compilan antes de empezar.
    compilar_traducciones()
