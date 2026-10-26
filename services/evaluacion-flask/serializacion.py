"""Arma el JSON de la respuesta de evaluación.

Para trazo, los campos del veredicto van en el orden de
ResultadoComparacionSerializer de contenido v1 (tests/test_contrato.py lo
comprueba). trazos-flask no devuelve `distancia_media` ni `razon_longitud`,
así que esos dos no aparecen.
"""

CAMPOS_TRAZO = ("aprobado", "puntaje", "motivo", "invertido", "detalle", "puntos_lejanos")


def resultado(r):
    datos = {"tipo": r.tipo, "caracter": r.caracter, "acerto": r.acerto}
    if r.tipo == "trazo":
        datos["secuencia"] = r.secuencia
        for campo in CAMPOS_TRAZO:
            if campo in r.detalle_trazo:
                datos[campo] = r.detalle_trazo[campo]
    return datos
