from django.db import models


class SesionEstudio(models.Model):
    """Sesión de práctica generada para un usuario en un momento dado.

    Solo persistencia: las reglas de cuándo se cierra o cuántos
    ejercicios quedan pendientes viven en tutor.domain.sesion_logic.
    """

    ESTADOS = [
        ("borrador", "Borrador"),
        ("activa", "Activa"),
        ("completada", "Completada"),
    ]

    usuario_id = models.UUIDField()
    nivel_hsk = models.PositiveSmallIntegerField()
    dificultad = models.PositiveSmallIntegerField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default="borrador")
    creada_en = models.DateTimeField(auto_now_add=True)
    duracion_estimada_min = models.PositiveSmallIntegerField(default=10)

    def __str__(self):
        return f"Sesión {self.pk} · usuario {self.usuario_id} · HSK{self.nivel_hsk}"


class Ejercicio(models.Model):
    """Ejercicio individual dentro de una sesión."""

    TIPOS = [
        ("trazo", "Orden de trazos"),
        ("pinyin", "Reconocer pinyin"),
        ("significado", "Significado"),
    ]

    sesion = models.ForeignKey(
        SesionEstudio, related_name="ejercicios", on_delete=models.CASCADE
    )
    caracter = models.CharField(max_length=8)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    dificultad = models.PositiveSmallIntegerField()
    es_refuerzo = models.BooleanField(
        default=False,
        help_text="True si nace de un error previo del usuario, no de contenido nuevo.",
    )

    respondido = models.BooleanField(default=False)
    fue_correcto = models.BooleanField(null=True, blank=True)
    respondido_en = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.caracter} ({self.tipo})"
