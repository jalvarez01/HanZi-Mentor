"""Análisis de una sílaba de pinyin: tono, inicial y final.

Funciones puras. Sirven para explicar un error (inicial o final distinta) y
para la nota de tono de una respuesta correcta. La evaluación no cambia: el
tono sigue sin contar (dominio/evaluacion.py).
"""

import unicodedata

# Marca combinante de cada tono, tras descomponer la vocal en NFD.
_TONOS = {"̄": 1, "́": 2, "̌": 3, "̀": 4}
_DIERESIS = "̈"

# Iniciales del pinyin; las de dos letras van primero para que "zh" gane a "z".
INICIALES = (
    "zh", "ch", "sh",
    "b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h",
    "j", "q", "x", "r", "z", "c", "s", "y", "w",
)


def tono(lectura):
    """1 a 4 según la marca de la vocal; 0 (tono neutro) si no tiene marca."""
    for caracter in unicodedata.normalize("NFD", lectura or ""):
        if caracter in _TONOS:
            return _TONOS[caracter]
    return 0


def sin_tono(texto):
    """Quita las marcas de tono y deja la ü: "lǜ" -> "lü"."""
    descompuesto = unicodedata.normalize("NFD", (texto or "").strip().lower())
    limpio = "".join(c for c in descompuesto if c not in _TONOS)
    return unicodedata.normalize("NFC", " ".join(limpio.split()))


def base(texto):
    """Forma de comparación, como la evaluación: sin tonos ni diéresis."""
    return sin_tono(texto).replace("ü", "u")


def separar(silaba):
    """("h", "ao") para "hao". La inicial vacía es una sílaba sin consonante
    inicial ("ai", "er")."""
    for inicial in INICIALES:
        if silaba.startswith(inicial):
            return inicial, silaba[len(inicial):]
    return "", silaba
