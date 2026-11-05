"""Todas las lecturas en pinyin de un carácter.

Make Me a Hanzi trae una sola lectura para la mayoría de los caracteres, así
que las demás salen de datos/lecturas_hsk.json, generado desde Unicode Unihan
(kXHC1983) con scripts/generar_lecturas.py. El servicio nunca descarga Unihan.
"""

import json
from functools import cache
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parent / "datos" / "lecturas_hsk.json"


@cache
def _tabla():
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))["lecturas"]
    except (OSError, ValueError, KeyError):
        return {}


def lecturas_de(hanzi, propias=()):
    """Las lecturas de Make Me a Hanzi primero y después las de Unihan, sin
    repetidas. Sin datos de Unihan quedan solo las propias."""
    resultado = []
    for lectura in [*propias, *_tabla().get(hanzi, [])]:
        if lectura and lectura not in resultado:
            resultado.append(lectura)
    return resultado
