"""Cajas del equipo aliado (VaultDrop) y el sorteo de un ítem.

VaultDrop publica cada caja con sus ítems y la probabilidad de cada uno
(suman 100). Abrir una caja aquí es un sorteo con esas mismas
probabilidades: no usa créditos ni cuentas de VaultDrop y no guarda nada.
"""

import random
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Item:
    nombre: str
    rareza: str
    valor_estimado: str  # texto con dos decimales, como lo publica VaultDrop
    imagen_url: str  # absoluta, o "" si no tiene
    probabilidad: Decimal  # en porcentaje: 0.5 es medio por ciento


@dataclass(frozen=True)
class Caja:
    id: int
    nombre: str
    precio: str
    imagen_url: str
    items: tuple


class CajaSinItems(Exception):
    """La caja no tiene ítems con probabilidad mayor que cero."""


def sortear(caja, rng=random):
    """Un ítem al azar según sus probabilidades. `rng` fija el azar en pruebas."""
    candidatos = [item for item in caja.items if item.probabilidad > 0]
    if not candidatos:
        raise CajaSinItems(caja.nombre)
    pesos = [float(item.probabilidad) for item in candidatos]
    return rng.choices(candidatos, weights=pesos, k=1)[0]
