"""Convierte los modelos en el JSON de la API, con los mismos campos y el
mismo orden que los serializers de v1 (agente-tutor/tutor/serializers.py).
tests/test_contrato.py lo comprueba."""

from datetime import timezone

from i18n import traducir


def _fecha(valor):
    """Como DateTimeField de DRF con TIME_ZONE='UTC': ISO 8601 con Z."""
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    texto = valor.astimezone(timezone.utc).isoformat()
    if texto.endswith("+00:00"):
        texto = texto[: -len("+00:00")] + "Z"
    return texto


def ejercicio(e):
    """EjercicioSerializer, más `patron` (RF-IA-03).

    `patron` es la única clave que no existe en v1 y va al final, así que las
    de v1 quedan iguales y en el mismo orden: el código del patrón de error
    que originó un ejercicio adaptado, o null.
    """
    return {
        "id": e.id,
        "caracter": e.caracter,
        "tipo": e.tipo,
        "dificultad": e.dificultad,
        "es_refuerzo": e.es_refuerzo,
        "patron": e.patron,
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


def desempeno(d):
    """Desempeño de una sesión (RF-IA-05). No existe en v1."""
    return {
        "sesion_id": d.sesion_id,
        "creada_en": _fecha(d.creada_en),
        "completada_en": _fecha(d.completada_en),
        "duracion_seg": d.duracion_seg,
        "duracion_estimada_min": d.duracion_estimada_min,
        "dentro_del_tiempo": d.dentro_del_tiempo,
        "segundos_por_ejercicio": d.segundos_por_ejercicio,
        "total": d.total,
        "aciertos": d.aciertos,
        "fallos": d.fallos,
        "tasa_acierto": d.tasa_acierto,
        "por_tipo": d.por_tipo,
    }


def historial(usuario_id, desempenos, totales):
    return {
        "usuario_id": str(usuario_id),
        "resumen": totales,
        "sesiones": [desempeno(d) for d in desempenos],
    }


def resultado_respuesta(r):
    """ResultadoRespuestaSerializer. Al final, dos claves que v1 no tiene:
    `desempeno` solo en la respuesta que cierra la sesión (RF-IA-05) y
    `aviso` solo si progreso no respondió."""
    datos = {
        "ejercicio": ejercicio(r["ejercicio"]),
        "sesion_completada": r["sesion_completada"],
        "pendientes": r["pendientes"],
        "proximo_repaso": r["proximo_repaso"],
        "tasa_acierto": r["tasa_acierto"],
    }
    if "desempeno" in r:
        datos["desempeno"] = desempeno(r["desempeno"])
    if "aviso" in r:
        datos["aviso"] = traducir(r["aviso"])
    return datos
