"""
Implementaciones intercambiables del motor de tutoría.

Ambas cumplen el mismo contrato, así el Service no sabe ni le importa
cuál está usando (Principio de Sustitución de Liskov + Inversión de
Dependencias).
"""

from abc import ABC, abstractmethod


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

    CATALOGO_POR_NIVEL = {
        1: ["人", "口", "日", "月", "水", "火"],
        2: ["学", "校", "老", "师", "同", "朋"],
        3: ["经", "济", "政", "府", "社", "会"],
        4: ["环", "境", "资", "源", "技", "术"],
        5: ["哲", "学", "逻", "辑", "概", "念"],
        6: ["宪", "法", "司", "法", "立", "法"],
    }

    def sugerir_dificultad(self, progreso: dict) -> int:
        tasa_acierto = progreso.get("tasa_acierto", 0.5)
        if tasa_acierto >= 0.85:
            return 4
        if tasa_acierto >= 0.6:
            return 3
        return 2

    def seleccionar_caracteres_nuevos(self, progreso: dict, cantidad: int) -> list:
        nivel = progreso.get("nivel_hsk", 1)
        dominados = set(progreso.get("caracteres_dominados", []))
        catalogo = self.CATALOGO_POR_NIVEL.get(nivel, [])
        disponibles = [c for c in catalogo if c not in dominados]
        return disponibles[:cantidad]


class MotorTutorLangGraph(MotorTutor):
    """Implementación real: delega el razonamiento al agente LangGraph."""

    def __init__(self, agente):
        self._agente = agente

    def sugerir_dificultad(self, progreso: dict) -> int:
        respuesta = self._agente.invoke(
            {"tarea": "sugerir_dificultad", "progreso": progreso}
        )
        return int(respuesta["dificultad"])

    def seleccionar_caracteres_nuevos(self, progreso: dict, cantidad: int) -> list:
        respuesta = self._agente.invoke(
            {
                "tarea": "seleccionar_caracteres",
                "progreso": progreso,
                "cantidad": cantidad,
            }
        )
        return respuesta["caracteres"]
