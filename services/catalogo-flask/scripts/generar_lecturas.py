"""Genera datos/lecturas_hsk.json: todas las lecturas en pinyin de los
caracteres HSK.

Make Me a Hanzi trae una sola lectura para la mayoría de los caracteres
(长 solo "zhǎng", 得 solo "dé"), así que las demás salen de Unicode Unihan:

1. kXHC1983: las lecturas del Xiandai Hanyu Cidian (diccionario moderno),
   con el formato "0121.040:cháng 1456.020:zhǎng";
2. si el carácter no tiene kXHC1983, kMandarin;
3. si tampoco tiene kMandarin, el pinyin de Make Me a Hanzi.

La lectura de Make Me a Hanzi va siempre primero (es el campo `pinyin` del
catálogo) y después las demás, sin repetidas y en el orden de la fuente.

El servicio nunca descarga Unihan: solo usa el JSON que deja este script.
Para regenerarlo, desde services/catalogo-flask:

    python scripts/generar_lecturas.py --diccionario <dictionary.txt de Make Me a Hanzi>
    python scripts/generar_lecturas.py --diccionario ... --unihan Unihan.zip

Sin --unihan descarga el Unihan.zip de la versión UNICODE_VERSION.
"""

import argparse
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from hsk import CARACTERES_POR_NIVEL  # noqa: E402

UNICODE_VERSION = "17.0.0"
URL_UNIHAN = f"https://www.unicode.org/Public/{UNICODE_VERSION}/ucd/Unihan.zip"
SALIDA = RAIZ / "datos" / "lecturas_hsk.json"
LICENCIA = (
    "Unicode License v3 (https://www.unicode.org/license.txt). "
    "Datos de Unicode Unihan, Copyright Unicode, Inc."
)
# "U+957F<TAB>kXHC1983<TAB>0121.040:cháng 1456.020:zhǎng"
LINEA = re.compile(r"^U\+([0-9A-F]+)\t(kXHC1983|kMandarin)\t(.+)$")


def sin_repetidas(lecturas):
    vistas, resultado = set(), []
    for lectura in lecturas:
        if lectura and lectura not in vistas:
            vistas.add(lectura)
            resultado.append(lectura)
    return resultado


def lecturas_xhc(valor):
    """De "0121.040:cháng 1456.020:zhǎng" a ["cháng", "zhǎng"]. Una entrada
    puede tener varias ubicaciones ("0001.010,0002.020:a") o un asterisco."""
    return sin_repetidas(parte.rsplit(":", 1)[1] for parte in valor.split() if ":" in parte)


def leer_unihan(origen):
    """{hanzi: {"kXHC1983": [...], "kMandarin": [...]}} de Unihan_Readings.txt."""
    if origen:
        datos = Path(origen).read_bytes()
    else:
        print(f"Descargando {URL_UNIHAN} ...")
        with urllib.request.urlopen(URL_UNIHAN, timeout=120) as respuesta:
            datos = respuesta.read()
    with zipfile.ZipFile(io.BytesIO(datos)) as zip_unihan:
        texto = zip_unihan.read("Unihan_Readings.txt").decode("utf-8")

    version = re.search(r"^# Unicode Version (\S+)", texto, re.M)
    lecturas = {}
    for linea in texto.splitlines():
        m = LINEA.match(linea)
        if not m:
            continue
        hanzi = chr(int(m.group(1), 16))
        valor = lecturas_xhc(m.group(3)) if m.group(2) == "kXHC1983" else m.group(3).split()
        lecturas.setdefault(hanzi, {})[m.group(2)] = valor
    return lecturas, version.group(1) if version else "desconocida"


def leer_makemeahanzi(ruta):
    """{hanzi: [pinyin, ...]} de dictionary.txt."""
    pinyin = {}
    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            try:
                dato = json.loads(linea)
            except ValueError:
                continue
            pinyin[dato["character"]] = list(dato.get("pinyin") or [])
    return pinyin


def generar(unihan, makemeahanzi, version):
    hsk = sorted({h for caracteres in CARACTERES_POR_NIVEL.values() for h in caracteres})
    conteo = {"kXHC1983": 0, "kMandarin": 0, "makemeahanzi": 0, "sin_datos": 0}
    lecturas = {}
    for hanzi in hsk:
        propias = makemeahanzi.get(hanzi, [])
        campos = unihan.get(hanzi, {})
        if campos.get("kXHC1983"):
            fuente, extra = "kXHC1983", campos["kXHC1983"]
        elif campos.get("kMandarin"):
            fuente, extra = "kMandarin", campos["kMandarin"]
        elif propias:
            fuente, extra = "makemeahanzi", []
        else:
            conteo["sin_datos"] += 1
            continue
        conteo[fuente] += 1
        lecturas[hanzi] = sin_repetidas(propias + extra)
    return {
        "fuente": (
            f"Unicode Unihan {version}, Unihan_Readings.txt: campo kXHC1983 "
            "(Xiandai Hanyu Cidian); si falta, kMandarin; si falta, el pinyin de "
            "Make Me a Hanzi. La lectura de Make Me a Hanzi va primero."
        ),
        "licencia": LICENCIA,
        "generado_con": "scripts/generar_lecturas.py",
        "conteo": conteo,
        "lecturas": lecturas,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--diccionario", required=True, help="dictionary.txt de Make Me a Hanzi.")
    parser.add_argument("--unihan", help=f"Unihan.zip local. Sin él se descarga {URL_UNIHAN}.")
    parser.add_argument("--salida", default=str(SALIDA))
    opciones = parser.parse_args(argv)

    unihan, version = leer_unihan(opciones.unihan)
    resultado = generar(unihan, leer_makemeahanzi(opciones.diccionario), version)
    Path(opciones.salida).write_text(
        json.dumps(resultado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    conteo = resultado["conteo"]
    varias = sum(1 for lista in resultado["lecturas"].values() if len(lista) > 1)
    print(f"{len(resultado['lecturas'])} caracteres en {opciones.salida} (Unihan {version}).")
    print(", ".join(f"{fuente}: {n}" for fuente, n in conteo.items()))
    print(f"Con más de una lectura: {varias}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
