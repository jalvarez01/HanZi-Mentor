"""Entidad del dominio: una oración de ejemplo que usa un carácter."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Ejemplo:
    """Oración en chino con su pinyin y su traducción.

    `pinyin` y `traduccion` pueden faltar: no todos los proveedores los traen
    para todas las oraciones.
    """

    texto: str
    pinyin: str | None = None
    traduccion: str | None = None

    def a_dict(self):
        return asdict(self)
