"""Caso de uso: validar un trazo dibujado contra la mediana esperada."""

from comparador import comparar_trazo
from i18n import traducir


def validar_trazo(solicitud):
    """Devuelve el cuerpo de la respuesta 200 según el contrato v2."""
    resultado = comparar_trazo(
        solicitud.puntos, solicitud.mediana, solicitud.ancho, solicitud.alto
    )
    return {
        "aprobado": resultado.aprobado,
        "puntaje": resultado.puntaje,
        "motivo": resultado.motivo,
        # El comparador deja el detalle en español; sale en el idioma pedido.
        "detalle": traducir(resultado.detalle),
        "invertido": resultado.invertido,
        "puntos_lejanos": resultado.puntos_lejanos,
        # Largo dibujado / largo esperado: con él, evaluacion-flask distingue
        # un trazo corto de uno largo (los dos llegan como "incompleto").
        "razon_longitud": round(resultado.razon_longitud, 3),
    }
