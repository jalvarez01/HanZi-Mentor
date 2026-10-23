"""Importa caracteres y trazos desde los archivos de Make Me a Hanzi.

Port del comando de Django services/contenido/caracteres/management/commands/
cargar_hanzi.py. La interfaz de línea de comandos está en cargar.py; acá
queda la lógica, para poder probarla.

Espera `dictionary.txt` y `graphics.txt` en la ruta indicada. Ambos son
listas de objetos JSON separados por saltos de línea, unibles por la clave
'character'.

Fuente: https://github.com/skishore/makemeahanzi (datos bajo licencias
Arphic y Unihan; ver el archivo COPYING del repositorio original).
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from hsk import CARACTERES_POR_NIVEL
from modelos import Caracter, Ejercicio, Trazo


class ErrorCarga(Exception):
    """Faltan archivos o los parámetros no seleccionan ningún carácter."""


@dataclass
class Resumen:
    creados: int = 0
    actualizados: int = 0
    borrados: int = 0
    con_nivel: int = 0
    sin_nivel: int = 0
    sin_datos: list = field(default_factory=list)


def leer_filtrado(archivo, deseados):
    """
    Lee línea por línea y guarda los caracteres que interesan.

    Se procesa en streaming, sin cargar el archivo entero en memoria:
    graphics.txt pesa varios MB. deseados=None significa quedarse con todos.
    """
    resultado = {}
    with Path(archivo).open(encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                dato = json.loads(linea)
            except json.JSONDecodeError:
                continue
            hanzi = dato.get("character")
            if hanzi and (deseados is None or hanzi in deseados):
                resultado[hanzi] = dato
    return resultado


def base_vacia(sesion):
    return sesion.scalar(select(func.count()).select_from(Caracter)) == 0


def _deseados(niveles, todos):
    if todos:
        return None
    deseados = set()
    for nivel in niveles:
        deseados.update(CARACTERES_POR_NIVEL.get(nivel, []))
    if not deseados:
        raise ErrorCarga(
            f"No hay caracteres definidos para los niveles {list(niveles)}. "
            "Usá --todos para importar sin filtrar."
        )
    return deseados


def _campos(dic):
    dic = dic or {}
    pinyin = dic.get("pinyin")
    return {
        "pinyin": pinyin[0] if pinyin else "",
        "definicion": dic.get("definition") or "",
        "radical": dic.get("radical") or "",
        "descomposicion": dic.get("decomposition") or "",
    }


def cargar(sesion, ruta, niveles=(1, 2), todos=False, limpiar=False):
    """Importa en una sola transacción y devuelve un Resumen."""
    ruta = Path(ruta)
    archivo_dic = ruta / "dictionary.txt"
    archivo_graf = ruta / "graphics.txt"
    for archivo in (archivo_dic, archivo_graf):
        if not archivo.exists():
            raise ErrorCarga(f"No se encontró {archivo}")

    # El nivel se asigna desde las listas HSK, estén o no en el filtro.
    nivel_de = {
        hanzi: nivel
        for nivel, caracteres in CARACTERES_POR_NIVEL.items()
        for hanzi in caracteres
    }

    deseados = _deseados(niveles, todos)
    definiciones = leer_filtrado(archivo_dic, deseados)
    graficos = leer_filtrado(archivo_graf, deseados)
    if deseados is None:
        # Con --todos, el universo es lo que traiga el archivo.
        deseados = set(definiciones) | set(graficos)

    resumen = Resumen()
    try:
        if limpiar:
            # Como el CASCADE de Django: los ejercicios dependen de los caracteres.
            sesion.execute(delete(Ejercicio))
            sesion.execute(delete(Trazo))
            resumen.borrados = sesion.execute(delete(Caracter)).rowcount

        existentes = {
            c.hanzi: c
            for c in sesion.scalars(
                select(Caracter)
                .where(Caracter.hanzi.in_(deseados))
                .options(selectinload(Caracter.trazos))
            )
        }

        for hanzi in sorted(deseados):
            dic = definiciones.get(hanzi)
            graf = graficos.get(hanzi)
            if dic is None and graf is None:
                resumen.sin_datos.append(hanzi)
                continue

            caracter = existentes.get(hanzi)
            if caracter is None:
                caracter = Caracter(hanzi=hanzi)
                sesion.add(caracter)
                resumen.creados += 1
            else:
                resumen.actualizados += 1

            for nombre, valor in _campos(dic).items():
                setattr(caracter, nombre, valor)
            caracter.nivel_hsk = nivel_de.get(hanzi)

            if graf:
                if caracter.trazos:
                    # Se borran antes de insertar los nuevos: (caracter, secuencia) es único.
                    caracter.trazos.clear()
                    sesion.flush()
                medianas = graf.get("medians", [])
                caracter.trazos = [
                    Trazo(
                        secuencia=i + 1,
                        path_svg=path,
                        mediana=medianas[i] if i < len(medianas) else [],
                    )
                    for i, path in enumerate(graf.get("strokes", []))
                ]

        sesion.flush()
        resumen.con_nivel = sesion.scalar(
            select(func.count()).select_from(Caracter).where(Caracter.nivel_hsk.is_not(None))
        )
        resumen.sin_nivel = sesion.scalar(
            select(func.count()).select_from(Caracter).where(Caracter.nivel_hsk.is_(None))
        )
        sesion.commit()
    except Exception:
        sesion.rollback()
        raise
    return resumen
