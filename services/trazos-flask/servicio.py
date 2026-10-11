"""Caso de uso: validar un trazo dibujado contra la mediana esperada."""

from comparador import comparar_trazo


def validar_trazo(solicitud):
    """Devuelve el cuerpo de la respuesta 200 según el contrato v2."""
    resultado = comparar_trazo(
        solicitud.puntos, solicitud.mediana, solicitud.ancho, solicitud.alto
    )
    return {
        "aprobado": resultado.aprobado,
        "puntaje": resultado.puntaje,
        "motivo": resultado.motivo,
        "detalle": resultado.detalle,
        "invertido": resultado.invertido,
        "puntos_lejanos": resultado.puntos_lejanos,
    }
