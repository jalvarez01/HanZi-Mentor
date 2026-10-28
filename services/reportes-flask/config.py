"""Configuración del servicio, leída siempre de variables de entorno.

Sigue el estándar de services/flask-base. No usa DATABASE_URL: los
resultados de las tareas viven en Redis con caducidad.

La leen la app Flask (app.py) y el worker de Celery (tareas.py), que usan
la misma imagen.
"""

import os


def _booleano(nombre, defecto="0"):
    return os.environ.get(nombre, defecto).strip().lower() in ("1", "true", "si")


def desde_entorno():
    return {
        "SERVICE_NAME": os.environ.get("SERVICE_NAME", "reportes-flask"),
        "HOST": os.environ.get("HOST", "0.0.0.0"),
        "PORT": int(os.environ.get("PORT", "5000")),
        "FLASK_DEBUG": _booleano("FLASK_DEBUG"),
        # Broker de Celery, backend de resultados y notificaciones.
        "REDIS_URL": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        # Segundos para conectar con Redis y esperar su respuesta en /health.
        "REDIS_TIMEOUT": float(os.environ.get("REDIS_TIMEOUT", "1")),
        # progreso-flask, que consulta la tarea de reporte. URL base sin /api/v2.
        "PROGRESO_URL": os.environ.get("PROGRESO_URL", "http://localhost:5083"),
        # Segundos por petición a progreso. Sin reintentos HTTP: reintenta Celery.
        "HTTP_TIMEOUT": float(os.environ.get("HTTP_TIMEOUT", "3")),
    }
