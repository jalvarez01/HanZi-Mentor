"""Geometría de un trazo a partir de su mediana (RF-IA-04).

Sistema de Make Me a Hanzi: lienzo de 1024, eje Y hacia arriba, contenido
entre y=-124 e y=900. Funciones puras: las usan el explicador de errores
(adaptadores/reglas.py) y la nota de mejora de un trazo aprobado
(dominio/notas.py).

`posicion` es la fracción del recorrido (0 al inicio, 1 al final), medida
por longitud de arco, igual que en los `puntos_lejanos` de trazos-flask.
"""

import math

from dominio.explicacion import Fragmento
from mensajes import N_

LIENZO = 1024
ARRIBA_Y = 900
# Tercios del lienzo para ubicar el inicio y el fin de un trazo.
TERCIO = LIENZO / 3

ZONAS = {
    ("arriba", "izquierda"): Fragmento(N_("arriba a la izquierda")),
    ("arriba", "centro"): Fragmento(N_("arriba al centro")),
    ("arriba", "derecha"): Fragmento(N_("arriba a la derecha")),
    ("medio", "izquierda"): Fragmento(N_("a media altura a la izquierda")),
    ("medio", "centro"): Fragmento(N_("en el centro")),
    ("medio", "derecha"): Fragmento(N_("a media altura a la derecha")),
    ("abajo", "izquierda"): Fragmento(N_("abajo a la izquierda")),
    ("abajo", "centro"): Fragmento(N_("abajo al centro")),
    ("abajo", "derecha"): Fragmento(N_("abajo a la derecha")),
}

# Ocho direcciones, cada una centrada en su ángulo (0 = hacia la derecha).
DIRECCIONES = (
    (0, Fragmento(N_("hacia la derecha"))),
    (45, Fragmento(N_("hacia arriba y a la derecha"))),
    (90, Fragmento(N_("hacia arriba"))),
    (135, Fragmento(N_("hacia arriba y a la izquierda"))),
    (180, Fragmento(N_("hacia la izquierda"))),
    (-135, Fragmento(N_("hacia abajo y a la izquierda"))),
    (-90, Fragmento(N_("hacia abajo"))),
    (-45, Fragmento(N_("hacia abajo y a la derecha"))),
)

# Partes del recorrido: principio, medio y final, con los cortes de siempre.
PARTES = ((0.34, "principio"), (0.66, "medio"), (1.01, "final"))

# Tramo del recorrido donde más se desvió el trazo, para insertar en una frase.
TRAMOS = {
    "principio": Fragmento(N_("al principio")),
    "medio": Fragmento(N_("en el medio")),
    "final": Fragmento(N_("al final")),
}

# Mitad de la ventana (fracción del recorrido) para la dirección local.
VENTANA_LOCAL = 0.15


def zona(punto):
    x, y = float(punto[0]), float(punto[1])
    desde_arriba = ARRIBA_Y - y
    fila = "arriba" if desde_arriba < TERCIO else "abajo" if desde_arriba > 2 * TERCIO else "medio"
    columna = "izquierda" if x < TERCIO else "derecha" if x > 2 * TERCIO else "centro"
    return ZONAS[(fila, columna)]


def direccion(inicio, fin):
    angulo = math.degrees(math.atan2(fin[1] - inicio[1], fin[0] - inicio[0]))

    def separacion(centro):
        return abs((angulo - centro + 180) % 360 - 180)

    return min(DIRECCIONES, key=lambda par: separacion(par[0]))[1]


def parte(posicion):
    """"principio", "medio" o "final" según la fracción del recorrido."""
    for limite, nombre in PARTES:
        if posicion < limite:
            return nombre
    return PARTES[-1][1]


def tramo(posicion):
    return TRAMOS[parte(posicion)]


def mediana_de(datos_correctos, secuencia):
    """La mediana del trazo con esa secuencia en el detalle del catálogo, o None."""
    for trazo in datos_correctos.get("trazos") or []:
        if trazo.get("secuencia") == secuencia:
            mediana = trazo.get("mediana")
            if isinstance(mediana, list) and len(mediana) >= 2:
                return mediana
    return None


def punto_en(mediana, fraccion):
    """El punto de la mediana a esa fracción de su longitud."""
    puntos = [(float(p[0]), float(p[1])) for p in mediana]
    tramos = list(zip(puntos, puntos[1:]))
    largos = [math.dist(a, b) for a, b in tramos]
    objetivo = max(0.0, min(1.0, fraccion)) * sum(largos)

    recorrido = 0.0
    for (a, b), largo in zip(tramos, largos):
        if largo > 0 and recorrido + largo >= objetivo:
            f = (objetivo - recorrido) / largo
            return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
        recorrido += largo
    return puntos[-1]


def direccion_general(mediana):
    """Dirección de punta a punta del trazo."""
    return direccion(mediana[0], mediana[-1])


def direccion_local(mediana, posicion, ventana=VENTANA_LOCAL):
    """Dirección del trazo alrededor de esa posición: del punto a
    `posicion - ventana` al punto a `posicion + ventana` (recortados a 0 y 1)."""
    return direccion(punto_en(mediana, posicion - ventana), punto_en(mediana, posicion + ventana))
