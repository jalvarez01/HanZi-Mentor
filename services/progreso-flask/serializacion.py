"""Convierte el progreso en el JSON de la API, igual que v1.

En agente-tutor la vista devuelve el dict del repositorio y DRF convierte
las fechas a ISO 8601 con Z. Acá se hace lo mismo a mano.
"""

from datetime import datetime, timezone

from i18n import traducir


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


def patron(p):
    """Un patrón de error (RF-IA-01). `titulo` y `consejo` salen en el idioma
    de la petición; `codigo` y `tipo` no cambian."""
    return {
        "codigo": p.codigo,
        "tipo": p.tipo,
        "frecuencia": p.frecuencia,
        "caracteres": list(p.caracteres),
        "ultima_vez": _fecha(p.ultima_vez),
        "titulo": traducir(p.titulo),
        "consejo": traducir(p.consejo),
    }


def repaso(r):
    """Un repaso agendado (RF-IA-02): {caracter, proximo_repaso, intervalo_dias, repeticiones}."""
    return {
        "caracter": r["caracter"],
        "proximo_repaso": _fecha(r["proximo_repaso"]),
        "intervalo_dias": r["intervalo_dias"],
        "repeticiones": r["repeticiones"],
    }


def fecha(valor):
    """Una fecha suelta en ISO 8601 con Z (o None)."""
    return _fecha(valor)
