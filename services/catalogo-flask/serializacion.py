"""Convierte los modelos en el JSON de la API.

Reemplaza a los serializers de salida de DRF y respeta exactamente sus
campos (ver services/contenido/*/serializers.py). tests/test_contrato.py
compara estas claves con las de v1.
"""

from datetime import timezone


def _fecha(valor):
    """Como DateTimeField de DRF con USE_TZ y TIME_ZONE='UTC': ISO 8601 con Z."""
    if valor.tzinfo is None:
        # SQLite no guarda la zona horaria: las fechas se escriben en UTC.
        valor = valor.replace(tzinfo=timezone.utc)
    texto = valor.astimezone(timezone.utc).isoformat()
    if texto.endswith("+00:00"):
        texto = texto[: -len("+00:00")] + "Z"
    return texto


def trazo(t):
    """TrazoSerializer."""
    return {"secuencia": t.secuencia, "path_svg": t.path_svg, "mediana": t.mediana}


def caracter_detalle(c):
    """CaracterSerializer: incluye los trazos en orden."""
    return {
        "hanzi": c.hanzi,
        "pinyin": c.pinyin,
        "definicion": c.definicion,
        "radical": c.radical,
        "descomposicion": c.descomposicion,
        "nivel_hsk": c.nivel_hsk,
        "trazos": [trazo(t) for t in c.trazos],
    }


def caracter_lista(c):
    """CaracterListaSerializer: versión liviana, sin trazos."""
    return {
        "hanzi": c.hanzi,
        "pinyin": c.pinyin,
        "definicion": c.definicion,
        "nivel_hsk": c.nivel_hsk,
    }


def ejercicio(e):
    """EjercicioSerializer."""
    return {
        "id": e.id,
        "tipo": e.tipo,
        "caracter": caracter_lista(e.caracter),
        "completado": e.completado,
    }


def leccion(lec):
    """LeccionSerializer."""
    return {
        "id": lec.id,
        "usuario_id": str(lec.usuario_id),
        "nivel_hsk": lec.nivel_hsk,
        "creada_en": _fecha(lec.creada_en),
        "ejercicios": [ejercicio(e) for e in lec.ejercicios],
    }
