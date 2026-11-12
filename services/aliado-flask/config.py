"""Configuración del servicio, leída siempre de variables de entorno.

Sigue el estándar de services/flask-base. Este servicio no guarda estado,
por eso no usa DATABASE_URL.
"""

import os


def _booleano(nombre, defecto="0"):
    return os.environ.get(nombre, defecto).strip().lower() in ("1", "true", "si")


def desde_entorno():
    return {
        "SERVICE_NAME": os.environ.get("SERVICE_NAME", "aliado-flask"),
        "HOST": os.environ.get("HOST", "0.0.0.0"),
        "PORT": int(os.environ.get("PORT", "5000")),
        "FLASK_DEBUG": _booleano("FLASK_DEBUG"),
        # Adaptador (ver adaptadores/fabrica.py): "vaultdrop" o "falso".
        "ALIADO_PROVEEDOR": os.environ.get("ALIADO_PROVEEDOR", "falso").strip().lower(),
        # URL base del aliado, sin /api: p. ej. http://<IP elástica de VaultDrop>.
        "ALIADO_URL": os.environ.get("ALIADO_URL", "").strip(),
        # Segundos que se espera al aliado antes de usar el respaldo.
        "ALIADO_TIMEOUT": float(os.environ.get("ALIADO_TIMEOUT", "3")),
    }
