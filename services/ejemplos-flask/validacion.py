"""Valida la forma de la entrada antes de llegar al caso de uso."""

from errores import ErrorDominio

IDIOMAS = ("es", "en")
LIMITE_DEFECTO = 5
LIMITE_MAXIMO = 10
MAX_CARACTERES = 4


def _es_hanzi(caracter):
    codigo = ord(caracter)
    # Ideogramas unificados CJK y su extensión A.
    return 0x4E00 <= codigo <= 0x9FFF or 0x3400 <= codigo <= 0x4DBF


def validar_consulta(hanzi, argumentos):
    """Devuelve (hanzi, idioma, limite) o lanza ErrorDominio con 400."""
    if not hanzi or len(hanzi) > MAX_CARACTERES or not all(_es_hanzi(c) for c in hanzi):
        raise ErrorDominio(
            f"Se espera de 1 a {MAX_CARACTERES} caracteres chinos",
            "ENTRADA_INVALIDA",
        )

    idioma = argumentos.get("lang", "es")
    if idioma not in IDIOMAS:
        raise ErrorDominio(
            f"Idioma no soportado: use {' o '.join(IDIOMAS)}",
            "ENTRADA_INVALIDA",
        )

    limite = argumentos.get("limite", str(LIMITE_DEFECTO))
    if not limite.isdigit() or not 1 <= int(limite) <= LIMITE_MAXIMO:
        raise ErrorDominio(
            f"El límite debe ser un entero entre 1 y {LIMITE_MAXIMO}",
            "ENTRADA_INVALIDA",
        )

    return hanzi, idioma, int(limite)
