from django.db import models
 
from caracteres.models import Caracter
 
TIPOS_EJERCICIO = [
    ("trazo", "Orden de trazos"),
    ("significado", "Significado"),
]
 
 
class Leccion(models.Model):
    """Agrupa un conjunto de Ejercicios generados para un nivel HSK."""
 
    usuario_id = models.PositiveIntegerField(db_index=True)
    nivel_hsk = models.PositiveSmallIntegerField()
    creada_en = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ["-creada_en"]
 
    def __str__(self):
        return f"Lección HSK{self.nivel_hsk} · usuario {self.usuario_id}"
 
    def generarContenido(self, cantidad=10, excluir=None):
        """
        Cumple el RF-APR-02: la entidad ejecuta generarContenido(). La
        orquestación real vive en LeccionService (Service Layer), esto
        es solo un delegado para no meter lógica de negocio en el Model.
        """
        from .services import LeccionService
 
        return LeccionService().generar_contenido(self, cantidad=cantidad, excluir=excluir)
 
 
class Ejercicio(models.Model):
    """Un ejercicio individual dentro de una Leccion, sobre un Caracter."""
 
    leccion = models.ForeignKey(
        Leccion, related_name="ejercicios", on_delete=models.CASCADE
    )
    caracter = models.ForeignKey(
        Caracter, related_name="ejercicios", on_delete=models.CASCADE
    )
    tipo = models.CharField(max_length=16, choices=TIPOS_EJERCICIO)
    completado = models.BooleanField(default=False)
 
    def __str__(self):
        return f"{self.get_tipo_display()} · {self.caracter.hanzi}"