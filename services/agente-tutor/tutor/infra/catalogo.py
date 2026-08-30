"""
Catálogo de caracteres — de dónde salen los hanzi que se enseñan.

Dos implementaciones bajo el mismo contrato:

- `CatalogoLocal`: lista fija en memoria. Sirve para tests y para levantar
  el servicio sin depender de que `contenido` esté arriba.
- `CatalogoRemoto`: consulta al servicio `contenido`, que a su vez sirve
  los datos importados de Make Me a Hanzi.

El remoto cae al local si la petición falla. Un servicio caído no debería
dejar al estudiante sin sesión.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 3


class Catalogo(ABC):
    @abstractmethod
    def caracteres_de_nivel(self, nivel, excluir=None, cantidad=4) -> list:
        """Devuelve hanzi del nivel pedido, omitiendo los excluidos."""


class CatalogoLocal(Catalogo):
    """Subconjunto en memoria. No depende de red ni de base de datos."""

    POR_NIVEL = {
        1: ["人", "口", "日", "月", "水", "火", "山", "大", "小", "中"],
        2: ["学", "校", "老", "师", "同", "朋", "友", "书", "本", "笔"],
        3: ["经", "济", "政", "府", "社", "会", "文", "化", "历", "史"],
        4: ["环", "境", "资", "源", "技", "术", "发", "展", "研", "究"],
        5: ["哲", "学", "逻", "辑", "概", "念", "理", "论", "思", "维"],
        6: ["宪", "法", "司", "立", "权", "利", "义", "务", "制", "度"],
    }

    def caracteres_de_nivel(self, nivel, excluir=None, cantidad=4) -> list:
        omitir = set(excluir or [])
        disponibles = self.POR_NIVEL.get(nivel, [])
        return [c for c in disponibles if c not in omitir][:cantidad]


class CatalogoRemoto(Catalogo):
    """Consulta el servicio de contenido por HTTP."""

    def __init__(self, base_url, respaldo=None):
        self._base_url = base_url.rstrip("/")
        self._respaldo = respaldo or CatalogoLocal()

    def caracteres_de_nivel(self, nivel, excluir=None, cantidad=4) -> list:
        omitir = list(excluir or [])

        try:
            import requests

            respuesta = requests.get(
                f"{self._base_url}/api/caracteres/",
                params={
                    "nivel": nivel,
                    "excluir": ",".join(omitir),
                    "limite": cantidad,
                },
                timeout=TIMEOUT_SEGUNDOS,
            )
            respuesta.raise_for_status()

            datos = respuesta.json().get("caracteres", [])
            hanzi = [d["hanzi"] for d in datos if d.get("hanzi")]

            if hanzi:
                return hanzi[:cantidad]

            logger.warning("El servicio de contenido no devolvió caracteres de HSK%s", nivel)

        except Exception as error:
            logger.warning("Falló la consulta al servicio de contenido: %s", error)

        return self._respaldo.caracteres_de_nivel(nivel, omitir, cantidad)
