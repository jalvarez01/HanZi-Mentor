"""Resumen público del catálogo para el equipo aliado (T14).

Es el "servicio a proveer" de la Entrega 2: un JSON con información relevante
de HanziMentor que otro equipo consume desde su aplicación. Solo lee la base
del catálogo y no expone nada de los usuarios.
"""

import random
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import func, select

from errores import ErrorDominio
from mensajes import N_
from modelos import ORDEN_CARACTERES, Caracter

NIVELES_HSK = range(1, 7)

# El carácter del día sale de la fecha: (día ordinal × primo) mód cantidad.
# Así es el mismo para todos durante el día y no avanza en orden alfabético.
_PRIMO = 7919


def resumen(sesion, nivel=None, ahora=None):
    """Totales del catálogo y un carácter del día.

    `nivel` (1 a 6) elige el carácter del día entre los de ese nivel HSK; los
    totales siempre son de todo el catálogo. `ahora` permite fijar la fecha
    en las pruebas.
    """
    ahora = ahora or datetime.now(timezone.utc)
    total = sesion.scalar(select(func.count()).select_from(Caracter))
    conteos = dict(
        sesion.execute(
            select(Caracter.nivel_hsk, func.count())
            .where(Caracter.nivel_hsk.is_not(None))
            .group_by(Caracter.nivel_hsk)
        ).all()
    )

    return {
        "sistema": "HanziMentor",
        "caracteres_totales": total,
        "por_nivel_hsk": {str(n): conteos.get(n, 0) for n in NIVELES_HSK},
        "caracter_del_dia": caracter_del_dia(sesion, ahora.date(), nivel),
        "generado_en": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def caracter_del_dia(sesion, fecha, nivel=None):
    """Un carácter con nivel HSK, el mismo durante toda la fecha (UTC).

    None si no hay caracteres cargados (o ninguno en ese nivel).
    """
    condicion = Caracter.nivel_hsk == nivel if nivel else Caracter.nivel_hsk.is_not(None)
    cantidad = sesion.scalar(select(func.count()).select_from(Caracter).where(condicion))
    if not cantidad:
        return None

    indice = (fecha.toordinal() * _PRIMO) % cantidad
    caracter = sesion.scalars(
        select(Caracter).where(condicion).order_by(*ORDEN_CARACTERES).offset(indice).limit(1)
    ).first()
    return {
        "hanzi": caracter.hanzi,
        "pinyin": caracter.pinyin,
        "definicion": caracter.definicion,
        "nivel_hsk": caracter.nivel_hsk,
    }


# --- Reto de pinyin para el equipo aliado ---------------------------------
#
# El aliado muestra un carácter con 4 lecturas posibles y pregunta cuál es
# la correcta. Las opciones falsas son el pinyin de otros caracteres del
# mismo nivel que no coinciden con ninguna lectura del carácter. Todo es sin
# estado: verificar solo necesita el carácter y la respuesta elegida.

OPCIONES = 4
PREGUNTA = N_("¿Cómo se lee %(hanzi)s?")


def _lecturas(caracter):
    return caracter.lecturas or ([caracter.pinyin] if caracter.pinyin else [])


def _normalizar(texto):
    # Compara con tono: "shì" y "shí" son opciones distintas.
    return unicodedata.normalize("NFC", (texto or "").strip().lower())


def reto(sesion, nivel=None, rng=random):
    """Un carácter al azar (del nivel, si se pide) con 4 opciones de pinyin.

    None si no hay caracteres en ese nivel. `rng` permite fijar el azar en
    las pruebas.
    """
    condicion = Caracter.nivel_hsk == nivel if nivel else Caracter.nivel_hsk.is_not(None)
    candidatos = sesion.scalars(
        select(Caracter).where(condicion, Caracter.pinyin != "").order_by(*ORDEN_CARACTERES)
    ).all()
    if not candidatos:
        return None

    elegido = rng.choice(candidatos)
    propias = {_normalizar(lectura) for lectura in _lecturas(elegido)}
    falsas = []
    for otro in rng.sample(candidatos, len(candidatos)):
        pinyin = otro.pinyin
        if _normalizar(pinyin) not in propias and pinyin not in falsas:
            falsas.append(pinyin)
        if len(falsas) == OPCIONES - 1:
            break

    opciones = [elegido.pinyin, *falsas]
    rng.shuffle(opciones)
    return {
        "hanzi": elegido.hanzi,
        "nivel_hsk": elegido.nivel_hsk,
        "pregunta": PREGUNTA,
        "opciones": opciones,
    }


def verificar_reto(sesion, hanzi, respuesta):
    """Si `respuesta` es una lectura del carácter. 404 si no existe."""
    caracter = sesion.scalars(select(Caracter).where(Caracter.hanzi == hanzi)).first()
    if caracter is None:
        raise ErrorDominio(N_("Carácter no encontrado."), "NO_ENCONTRADO", estado=404)

    lecturas = _lecturas(caracter)
    return {
        "hanzi": caracter.hanzi,
        "respuesta": respuesta,
        "correcta": _normalizar(respuesta) in {_normalizar(x) for x in lecturas},
        "pinyin": caracter.pinyin,
        "lecturas": lecturas,
        "definicion": caracter.definicion,
    }
