"""Puerto (interfaz) hacia quien explica los errores del usuario (RF-IA-04).

Patrón Adapter con Inversión de Dependencias, igual que ProveedorEjemplos en
ejemplos-flask: el caso de uso depende de esta interfaz y cada forma de
explicar es un adaptador en `adaptadores/`. La fábrica elige cuál según
EXPLICADOR_ERRORES. Hoy hay uno determinista ("reglas"); uno con un modelo
de lenguaje se puede sumar sin tocar el dominio ni el caso de uso.
"""

from abc import ABC, abstractmethod


class ExplicadorErrores(ABC):
    """Convierte un error del usuario en una explicación pedagógica."""

    #: Nombre corto del adaptador (el valor de EXPLICADOR_ERRORES).
    nombre = "desconocido"

    @abstractmethod
    def explicar_error(self, tipo, error):
        """Devuelve una `Explicacion` para `error` (un `ErrorEvaluado`).

        `tipo` es "trazo", "pinyin" o "significado". Si la respuesta es
        correcta, o no hay nada preciso que decir, devuelve None.
        """
