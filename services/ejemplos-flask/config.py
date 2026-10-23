"""Configuración del servicio, leída siempre de variables de entorno.

Sigue el estándar de services/flask-base. Este servicio no guarda estado,
por eso no usa DATABASE_URL.
"""

import os


def _booleano(nombre, defecto="0"):
    return os.environ.get(nombre, defecto).strip().lower() in ("1", "true", "si")


def desde_entorno():
    return {
        "SERVICE_NAME": os.environ.get("SERVICE_NAME", "ejemplos-flask"),
        "HOST": os.environ.get("HOST", "0.0.0.0"),
        "PORT": int(os.environ.get("PORT", "5000")),
        "FLASK_DEBUG": _booleano("FLASK_DEBUG"),
        # Adaptador que se inyecta en el caso de uso (ver adaptadores/fabrica.py).
        "PROVEEDOR_EJEMPLOS": os.environ.get("PROVEEDOR_EJEMPLOS", "falso").strip().lower(),
    }
