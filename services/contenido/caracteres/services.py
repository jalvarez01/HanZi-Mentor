"""
Capa de Aplicación — orquesta la validación de un trazo dibujado.

La vista no sabe nada de modelos ni del algoritmo de comparación: solo
llama a este servicio. El servicio busca los datos y delega la lógica
de comparación al dominio (domain/comparador.py, vía el modelo Trazo).
"""

from .domain.exceptions import CaracterNoEncontradoError, TrazoNoEncontradoError
from .models import Caracter, Trazo


class ValidacionTrazoService:
    """Valida el trazo dibujado por el usuario contra la mediana oficial."""

    def validar(self, hanzi, secuencia, puntos, ancho, alto):
        caracter = Caracter.objects.filter(hanzi=hanzi).first()
        if caracter is None:
            raise CaracterNoEncontradoError(
                f"No existe el carácter '{hanzi}'."
            )

        trazo = Trazo.objects.filter(caracter=caracter, secuencia=secuencia).first()
        if trazo is None:
            raise TrazoNoEncontradoError(
                f"El carácter '{hanzi}' no tiene un trazo con secuencia {secuencia}."
            )

        return trazo.comparar_con_trazo_usuario(puntos, ancho, alto)
