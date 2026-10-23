"""Convierte el progreso en el JSON de la API, igual que v1.

En agente-tutor la vista devuelve el dict del repositorio y DRF convierte
las fechas a ISO 8601 con Z. Acá se hace lo mismo a mano.
"""

from datetime import datetime, timezone


def _fecha(valor):
    """Como el JSONEncoder de DRF con TIME_ZONE='UTC': ISO 8601 con Z."""
    if valor is None:
        return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    texto = valor.astimezone(timezone.utc).isoformat()
    if texto.endswith("+00:00"):
        texto = texto[: -len("+00:00")] + "Z"
    return texto


def progreso(datos):
    """Copia del dict del repositorio con las fechas en texto. Mantiene el orden."""
    return {
        clave: _fecha(valor) if isinstance(valor, datetime) else valor
        for clave, valor in datos.items()
    }
