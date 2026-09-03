import random

from caracteres.hsk import caracteres_hasta
from caracteres.models import Caracter

from .factories import EjercicioFactory


class LeccionBuilder:
    """
    Builder: construye el contenido de la entidad más compleja del sistema
    (Leccion -> N Ejercicios, cada uno atado a un Caracter) paso a paso.
    """

    def __init__(self, leccion):
        self._leccion = leccion
        self._caracteres = []
        self._ejercicios = []

    def con_caracteres_del_nivel(self, cantidad=10, excluir=None):
        excluir = excluir or []
        hanzis = [h for h in caracteres_hasta(self._leccion.nivel_hsk) if h not in excluir]
        random.shuffle(hanzis)
        hanzis = hanzis[:cantidad]
        self._caracteres = list(Caracter.objects.filter(hanzi__in=hanzis))
        return self

    def con_ejercicios_variados(self, tipos=("trazo", "significado")):
        for caracter in self._caracteres:
            ejercicio = EjercicioFactory.crear(
                tipo=random.choice(tipos),
                leccion=self._leccion,
                caracter=caracter,
            )
            self._ejercicios.append(ejercicio)
        return self

    def build(self):
        return self._ejercicios