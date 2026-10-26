"""Valida la forma de la entrada de POST /api/v2/evaluacion/.

Cada error se lanza como ErrorDominio con 400 y código ENTRADA_INVALIDA.
Los puntos del trazo solo se revisan por encima (que sea una lista): el
detalle de cada punto lo valida trazos-flask, y su 400 se devuelve igual.
"""

from dataclasses import dataclass

from dominio.evaluacion import UMBRALES_SIGNIFICADO
from errores import ErrorDominio

TIPOS = ("pinyin", "significado", "trazo")

# En v1 la dificultad sale del ejercicio guardado; acá llega en el cuerpo.
# Solo cambia el umbral del significado.
DIFICULTAD_DEFECTO = 3
MAX_CARACTER = 8
MAX_RESPUESTA = 200


@dataclass
class SolicitudEvaluacion:
    tipo: str
    caracter: str
    dificultad: int
    respuesta: object


@dataclass
class RespuestaTrazo:
    secuencia: int
    puntos: list
    ancho: int
    alto: int


def _invalida(mensaje):
    return ErrorDominio(mensaje, "ENTRADA_INVALIDA")


def _entero_positivo(valor):
    return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0


def _respuesta_texto(valor):
    if not isinstance(valor, str):
        raise _invalida("'respuesta' debe ser un texto para pinyin y significado")
    if len(valor) > MAX_RESPUESTA:
        raise _invalida(f"'respuesta' supera los {MAX_RESPUESTA} caracteres")
    return valor


def _respuesta_trazo(valor):
    if not isinstance(valor, dict):
        raise _invalida("'respuesta' debe ser un objeto con secuencia, puntos, ancho y alto")

    faltantes = [c for c in ("secuencia", "puntos", "ancho", "alto") if c not in valor]
    if faltantes:
        raise _invalida(f"Faltan campos en 'respuesta': {', '.join(faltantes)}")
    if not _entero_positivo(valor["secuencia"]):
        raise _invalida("'secuencia' debe ser un entero mayor o igual a 1")
    if not isinstance(valor["puntos"], list):
        raise _invalida("'puntos' debe ser una lista de puntos")
    for campo in ("ancho", "alto"):
        if not _entero_positivo(valor[campo]):
            raise _invalida(f"'{campo}' debe ser un entero positivo")

    return RespuestaTrazo(valor["secuencia"], valor["puntos"], valor["ancho"], valor["alto"])


def validar_evaluacion(datos):
    if not isinstance(datos, dict):
        raise _invalida("El cuerpo debe ser un objeto JSON")

    faltantes = [c for c in ("tipo", "caracter", "respuesta") if c not in datos]
    if faltantes:
        raise _invalida(f"Faltan campos: {', '.join(faltantes)}")

    tipo = datos["tipo"]
    if tipo not in TIPOS:
        raise _invalida(f"'tipo' debe ser uno de: {', '.join(TIPOS)}")

    caracter = datos["caracter"]
    if not isinstance(caracter, str) or not caracter.strip():
        raise _invalida("'caracter' debe ser un texto no vacío")
    caracter = caracter.strip()
    if len(caracter) > MAX_CARACTER:
        raise _invalida(f"'caracter' supera los {MAX_CARACTER} caracteres")

    dificultad = datos.get("dificultad", DIFICULTAD_DEFECTO)
    if isinstance(dificultad, bool) or dificultad not in UMBRALES_SIGNIFICADO:
        raise _invalida("'dificultad' debe ser un entero entre 1 y 5")

    if tipo == "trazo":
        respuesta = _respuesta_trazo(datos["respuesta"])
    else:
        respuesta = _respuesta_texto(datos["respuesta"])

    return SolicitudEvaluacion(tipo, caracter, dificultad, respuesta)
