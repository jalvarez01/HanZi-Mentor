"""Validación de la forma del JSON de entrada."""

import math
from dataclasses import dataclass

from mensajes import N_


class EntradaInvalida(Exception):
    """La petición no cumple el contrato; se traduce a HTTP 400.

    `mensaje` va en español, marcado con N_; `params` completa sus marcadores.
    errores.py lo traduce al idioma de la petición.
    """

    def __init__(self, mensaje, params=None):
        self.plantilla = mensaje
        self.params = params or {}
        super().__init__(mensaje % self.params if self.params else mensaje)


@dataclass
class SolicitudTrazo:
    mediana: list
    puntos: list
    ancho: int
    alto: int


def validar_solicitud(cuerpo, max_puntos):
    if not isinstance(cuerpo, dict):
        raise EntradaInvalida(N_("El cuerpo debe ser un objeto JSON"))

    faltantes = [c for c in ("mediana", "puntos", "ancho", "alto") if c not in cuerpo]
    if faltantes:
        raise EntradaInvalida(N_("Faltan campos: %(campos)s"), {"campos": ", ".join(faltantes)})

    return SolicitudTrazo(
        mediana=_validar_lista_puntos(cuerpo["mediana"], "mediana", max_puntos),
        puntos=_validar_lista_puntos(cuerpo["puntos"], "puntos", max_puntos),
        ancho=_validar_entero_positivo(cuerpo["ancho"], "ancho"),
        alto=_validar_entero_positivo(cuerpo["alto"], "alto"),
    )


def _validar_lista_puntos(valor, nombre, max_puntos):
    if not isinstance(valor, list):
        raise EntradaInvalida(N_("'%(campo)s' debe ser una lista de puntos"), {"campo": nombre})
    if len(valor) < 2:
        raise EntradaInvalida(N_("'%(campo)s' necesita al menos 2 puntos"), {"campo": nombre})
    if len(valor) > max_puntos:
        raise EntradaInvalida(
            N_("'%(campo)s' supera el máximo de %(maximo)s puntos"),
            {"campo": nombre, "maximo": max_puntos},
        )
    return [_validar_punto(p, nombre, i) for i, p in enumerate(valor)]


def _validar_punto(punto, nombre, indice):
    """Acepta [x, y] o {"x": x, "y": y}; siempre devuelve [x, y]."""
    if isinstance(punto, dict):
        if "x" not in punto or "y" not in punto:
            raise EntradaInvalida(
                N_("'%(campo)s[%(indice)s]' debe tener 'x' e 'y'"),
                {"campo": nombre, "indice": indice},
            )
        coordenadas = [punto["x"], punto["y"]]
    elif isinstance(punto, list) and len(punto) == 2:
        coordenadas = punto
    else:
        raise EntradaInvalida(
            N_("'%(campo)s[%(indice)s]' debe ser [x, y] o {\"x\", \"y\"}"),
            {"campo": nombre, "indice": indice},
        )

    if not all(_es_numero(c) for c in coordenadas):
        raise EntradaInvalida(
            N_("'%(campo)s[%(indice)s]' tiene coordenadas no numéricas"),
            {"campo": nombre, "indice": indice},
        )
    return [float(c) for c in coordenadas]


def _es_numero(valor):
    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and math.isfinite(valor)
    )


def _validar_entero_positivo(valor, nombre):
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise EntradaInvalida(N_("'%(campo)s' debe ser un entero positivo"), {"campo": nombre})
    return valor
