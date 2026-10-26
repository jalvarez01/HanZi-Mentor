"""Configuración del servicio, leída siempre de variables de entorno.

Sigue el estándar de services/flask-base. Este servicio no guarda estado,
por eso no usa DATABASE_URL (igual que trazos-flask).
"""

import os


def _booleano(nombre, defecto="0"):
    return os.environ.get(nombre, defecto).strip().lower() in ("1", "true", "si")


def desde_entorno():
    return {
        "SERVICE_NAME": os.environ.get("SERVICE_NAME", "evaluacion-flask"),
        "HOST": os.environ.get("HOST", "0.0.0.0"),
        "PORT": int(os.environ.get("PORT", "5000")),
        "FLASK_DEBUG": _booleano("FLASK_DEBUG"),
        # Servicios de los que depende, por HTTP. URL base sin /api/v2.
        "CATALOGO_URL": os.environ.get("CATALOGO_URL", "http://localhost:5081"),
        "TRAZOS_URL": os.environ.get("TRAZOS_URL", "http://localhost:5082"),
        # Segundos por petición y reintentos de los GET (ver clientes.py).
        "HTTP_TIMEOUT": float(os.environ.get("HTTP_TIMEOUT", "3")),
        "HTTP_REINTENTOS": int(os.environ.get("HTTP_REINTENTOS", "2")),
    }
