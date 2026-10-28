"""Arma el JSON del reporte de progreso (acordado en la fase 0 de T19).

Todos los campos salen de GET /api/v2/progreso/<id>/ de progreso-flask,
salvo `generado_en`. Se dejan fuera `errores_frecuentes` y
`aciertos_consecutivos`: son contadores internos y `caracteres_debiles` ya
los resume.
"""

from datetime import timezone

CAMPOS_DE_PROGRESO = (
    "usuario_id",
    "nivel_hsk",
    "nivel_max_desbloqueado",
    "tasa_acierto",
    "total_dominados",
    "total_por_reforzar",
    "caracteres_dominados",
    "caracteres_debiles",
    "proximo_repaso",
    "actualizado_en",
)


def fecha_iso(momento):
    """ISO 8601 en UTC con Z, igual que las fechas de progreso-flask."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    texto = momento.astimezone(timezone.utc).isoformat()
    if texto.endswith("+00:00"):
        texto = texto[: -len("+00:00")] + "Z"
    return texto


def armar_reporte(progreso, generado_en):
    """Copia los campos acordados en orden y agrega `generado_en`."""
    reporte = {campo: progreso.get(campo) for campo in CAMPOS_DE_PROGRESO}
    reporte["generado_en"] = fecha_iso(generado_en)
    return reporte
