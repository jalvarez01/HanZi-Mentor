"""Armado de lecciones: Builder y Factory de ejercicios.

Port de services/contenido/lecciones/domain/ (builders.py y factories.py).
En Django el Builder consultaba la base directamente; acá recibe los
candidatos ya consultados (servicio.py hace la consulta), así el dominio
no depende de SQLAlchemy y se prueba con listas en memoria.
"""

import random
from dataclasses import dataclass

# Tipo de ejercicio -> nombre legible (los choices del modelo Django).
TIPOS_EJERCICIO = {
    "trazo": "Orden de trazos",
    "significado": "Significado",
}


@dataclass(frozen=True)
class PlanEjercicio:
    """Un ejercicio decidido por el dominio, antes de guardarse."""

    tipo: str
    caracter: object


class EjercicioFactory:
    """
    Factory: encapsula la creación de las distintas variantes de Ejercicio.
    Si mañana aparece un tipo nuevo (pinyin, opción múltiple), solo se
    extiende esta clase, sin tocar el Builder ni el servicio.
    """

    @staticmethod
    def crear(tipo, caracter):
        if tipo not in TIPOS_EJERCICIO:
            raise ValueError(f"Tipo de ejercicio inválido: {tipo}")
        return PlanEjercicio(tipo=tipo, caracter=caracter)


class LeccionBuilder:
    """
    Builder: construye el contenido de la entidad más compleja del sistema
    (Leccion -> N Ejercicios, cada uno atado a un Caracter) paso a paso.
    """

    def __init__(self, aleatorio=None):
        self._aleatorio = aleatorio or random.Random()
        self._caracteres = []
        self._ejercicios = []

    def con_caracteres_del_nivel(self, del_nivel, sin_clasificar, cantidad=10):
        """
        Selecciona los caracteres de la lección. Prioridad:

        1. `del_nivel`: caracteres clasificados exactamente en el nivel de la
           lección (nunca de otro nivel: un carácter con nivel_hsk=1 no debe
           aparecer en una lección HSK5, ni viceversa).
        2. Si no alcanzan para completar `cantidad`, se rellena con
           `sin_clasificar` (nivel_hsk NULL), que pueden aparecer en
           cualquier nivel.
        """
        del_nivel = list(del_nivel)
        self._aleatorio.shuffle(del_nivel)
        seleccionados = del_nivel[:cantidad]

        faltantes = cantidad - len(seleccionados)
        if faltantes > 0:
            relleno = list(sin_clasificar)
            self._aleatorio.shuffle(relleno)
            seleccionados += relleno[:faltantes]

        self._caracteres = seleccionados
        return self

    def con_ejercicios_variados(self, tipos=tuple(TIPOS_EJERCICIO)):
        for caracter in self._caracteres:
            plan = EjercicioFactory.crear(
                tipo=self._aleatorio.choice(tipos),
                caracter=caracter,
            )
            self._ejercicios.append(plan)
        return self

    def build(self):
        return self._ejercicios
