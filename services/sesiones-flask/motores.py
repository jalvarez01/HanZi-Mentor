"""
Motor del tutor: decide la dificultad y qué caracteres nuevos practicar.

Port de MotorTutor y MotorTutorMock de agente-tutor/tutor/infra/motores.py.
El motor no guarda su propia lista de caracteres: los pide al catálogo que
recibe inyectado (CatalogoRemoto, con su lista local de respaldo).

El motor con LangGraph (MotorTutorLangGraph) sigue en agente-tutor y no se
porta: depende del agente y de sus credenciales. fabricas.py solo arma MOCK.
"""

from abc import ABC, abstractmethod

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

    def __init__(self, catalogo):
        self._catalogo = catalogo

    def sugerir_dificultad(self, progreso: dict) -> int:
        tasa = progreso.get("tasa_acierto", 0.5)
        if tasa >= UMBRAL_ALTO:
            return 4
        if tasa >= UMBRAL_MEDIO:
            return 3
        return 2

    def seleccionar_caracteres_nuevos(self, progreso: dict, cantidad: int) -> list:
        # Igual que v1: el nivel sale del progreso del usuario.
        return self._catalogo.caracteres_de_nivel(
            nivel=progreso.get("nivel_hsk", 1),
            excluir=progreso.get("caracteres_dominados", []),
            cantidad=cantidad,
        )
