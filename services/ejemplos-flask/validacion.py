"""Valida la forma de la entrada antes de llegar al caso de uso."""

from errores import ErrorDominio
from mensajes import N_

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
            N_("Se espera de 1 a %(maximo)s caracteres chinos"),
            "ENTRADA_INVALIDA",
            params={"maximo": MAX_CARACTERES},
        )

    idioma = argumentos.get("lang", "es")
    if idioma not in IDIOMAS:
        raise ErrorDominio(
            N_("Idioma no soportado: use %(idiomas)s"),
            "ENTRADA_INVALIDA",
            # Lista neutra (sin "o") para que se pueda traducir igual.
            params={"idiomas": ", ".join(IDIOMAS)},
        )

    limite = argumentos.get("limite", str(LIMITE_DEFECTO))
    if not limite.isdigit() or not 1 <= int(limite) <= LIMITE_MAXIMO:
        raise ErrorDominio(
            N_("El límite debe ser un entero entre 1 y %(maximo)s"),
            "ENTRADA_INVALIDA",
            params={"maximo": LIMITE_MAXIMO},
        )

    return hanzi, idioma, int(limite)
