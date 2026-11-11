"""Planes de HanZi Mentor (RF-USR-01).

Free es el plan por defecto: lo tiene todo usuario que nunca pagó y vuelve
solo cuando Premium vence. Premium se paga por periodos de 30 días y
desbloquea los niveles HSK 4 a 6.
"""

from dataclasses import dataclass

from mensajes import N_

FREE = "free"
PREMIUM = "premium"

PERIODO_DIAS = 30
# Renovar solo se puede cuando faltan estos días o menos para el vencimiento.
# Es menor que PERIODO_DIAS a propósito: con la misma cifra, renovar se podía
# justo después de activar y se pagaban dos periodos seguidos.
VENTANA_RENOVACION_DIAS = 7
MONEDA = "COP"


@dataclass(frozen=True)
class Plan:
    codigo: str
    nombre: str  # en español, marcado con N_
    descripcion: str  # en español, marcado con N_
    precio: int  # por periodo, en pesos colombianos sin decimales
    nivel_maximo: int  # último nivel HSK que se puede practicar


PLANES = {
    FREE: Plan(
        FREE,
        N_("Gratis"),
        N_("Practicá los niveles HSK 1 a 3."),
        0,
        3,
    ),
    PREMIUM: Plan(
        PREMIUM,
        N_("Premium"),
        N_("Todos los niveles, de HSK 1 a 6, por 30 días."),
        14900,
        6,
    ),
}
