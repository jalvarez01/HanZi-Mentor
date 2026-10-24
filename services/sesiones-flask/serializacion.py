"""Convierte los modelos en el JSON de la API, con los mismos campos y el
mismo orden que los serializers de v1 (agente-tutor/tutor/serializers.py).
tests/test_contrato.py lo comprueba."""

from datetime import timezone


def _fecha(valor):
    """Como DateTimeField de DRF con TIME_ZONE='UTC': ISO 8601 con Z."""
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    texto = valor.astimezone(timezone.utc).isoformat()
    if texto.endswith("+00:00"):
        texto = texto[: -len("+00:00")] + "Z"
    return texto


def ejercicio(e):
    """EjercicioSerializer."""
    return {
        "id": e.id,
        "caracter": e.caracter,
        "tipo": e.tipo,
        "dificultad": e.dificultad,
        "es_refuerzo": e.es_refuerzo,
    }


def sesion(s):
    """SesionEstudioSerializer."""
    return {
        "id": s.id,
        "usuario_id": str(s.usuario_id),
        "nivel_hsk": s.nivel_hsk,
        "dificultad": s.dificultad,
        "estado": s.estado,
        "duracion_estimada_min": s.duracion_estimada_min,
        "creada_en": _fecha(s.creada_en),
        "ejercicios": [ejercicio(e) for e in s.ejercicios],
    }


def resultado_respuesta(r):
    """ResultadoRespuestaSerializer. `aviso` solo aparece si progreso no respondió."""
    datos = {
        "ejercicio": ejercicio(r["ejercicio"]),
        "sesion_completada": r["sesion_completada"],
        "pendientes": r["pendientes"],
        "proximo_repaso": r["proximo_repaso"],
        "tasa_acierto": r["tasa_acierto"],
    }
    if "aviso" in r:
        datos["aviso"] = r["aviso"]
    return datos
