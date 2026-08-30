"""
Implementaciones intercambiables del motor de tutoría.

Ambas cumplen el mismo contrato, así el Service no sabe ni le importa
cuál está usando (Sustitución de Liskov + Inversión de Dependencias).

Ninguna de las dos guarda su propia lista de caracteres: las dos piden el
contenido al Catalogo que reciben inyectado.
"""

from abc import ABC, abstractmethod

from .catalogo import CatalogoLocal

UMBRAL_ALTO = 0.85
UMBRAL_MEDIO = 0.6


class MotorTutor(ABC):
    """Contrato que toda implementación del tutor debe cumplir."""

    @abstractmethod
    def sugerir_dificultad(self, progreso: dict) -> int:
        """Devuelve una dificultad de 1 a 5."""

    @abstractmethod
    def seleccionar_caracteres_nuevos(self, progreso: dict, cantidad: int) -> list:
        """Devuelve los caracteres nuevos a practicar."""


class MotorTutorMock(MotorTutor):
    """Implementación determinista para desarrollo, tests y demos sin costo."""

    def __init__(self, catalogo=None):
        self._catalogo = catalogo or CatalogoLocal()

    def sugerir_dificultad(self, progreso: dict) -> int:
        tasa = progreso.get("tasa_acierto", 0.5)
        if tasa >= UMBRAL_ALTO:
            return 4
        if tasa >= UMBRAL_MEDIO:
            return 3
        return 2

    def seleccionar_caracteres_nuevos(self, progreso: dict, cantidad: int) -> list:
        return self._catalogo.caracteres_de_nivel(
            nivel=progreso.get("nivel_hsk", 1),
            excluir=progreso.get("caracteres_dominados", []),
            cantidad=cantidad,
        )


class MotorTutorLangGraph(MotorTutor):
    """Implementación real: delega el razonamiento al agente LangGraph."""

    def __init__(self, agente, catalogo=None):
        self._agente = agente
        self._catalogo = catalogo or CatalogoLocal()

    def sugerir_dificultad(self, progreso: dict) -> int:
        respuesta = self._agente.invoke(
            {"tarea": "sugerir_dificultad", "progreso": progreso}
        )
        return int(respuesta["dificultad"])

    def seleccionar_caracteres_nuevos(self, progreso: dict, cantidad: int) -> list:
        # El catálogo acota el universo; el agente elige dentro de ese universo.
        disponibles = self._catalogo.caracteres_de_nivel(
            nivel=progreso.get("nivel_hsk", 1),
            excluir=progreso.get("caracteres_dominados", []),
            cantidad=cantidad * 3,
        )

        respuesta = self._agente.invoke({
            "tarea": "seleccionar_caracteres",
            "progreso": {**progreso, "disponibles": disponibles},
            "cantidad": cantidad,
        })

        elegidos = respuesta.get("caracteres", [])
        return elegidos[:cantidad] if elegidos else disponibles[:cantidad]
