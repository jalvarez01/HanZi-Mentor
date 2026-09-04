import random

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
        """
        Selecciona caracteres para la lección según el nivel_hsk real en BD
        (no una lista hardcodeada de referencia). Prioridad:

        1. Caracteres clasificados exactamente en el nivel de la lección
           (nunca de otro nivel: un caracter con nivel_hsk=1 no debe
           aparecer en una lección HSK5, ni viceversa).
        2. Si no alcanzan para completar `cantidad`, se rellena con
           caracteres sin clasificar (nivel_hsk NULL) — estos sí pueden
           aparecer en cualquier nivel.
        """
        excluir = excluir or []
        nivel = self._leccion.nivel_hsk

        del_nivel = list(
            Caracter.objects.filter(nivel_hsk=nivel).exclude(hanzi__in=excluir)
        )
        random.shuffle(del_nivel)
        seleccionados = del_nivel[:cantidad]

        faltantes = cantidad - len(seleccionados)
        if faltantes > 0:
            sin_clasificar = list(
                Caracter.objects.filter(nivel_hsk__isnull=True).exclude(hanzi__in=excluir)
            )
            random.shuffle(sin_clasificar)
            seleccionados += sin_clasificar[:faltantes]

        self._caracteres = seleccionados
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