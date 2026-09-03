from django.db import transaction
 
from .domain.builders import LeccionBuilder
from .models import Ejercicio
 
 
class LeccionService:
    """
    Service Layer: orquesta el flujo de negocio de generación de contenido.
    Toda la lógica vive aquí, no en el Model ni en la View.
    """
 
    @transaction.atomic
    def generar_contenido(self, leccion, cantidad=10, excluir=None):
        ejercicios = (
            LeccionBuilder(leccion)
            .con_caracteres_del_nivel(cantidad=cantidad, excluir=excluir)
            .con_ejercicios_variados()
            .build()
        )
        Ejercicio.objects.bulk_create(ejercicios)
        return ejercicios