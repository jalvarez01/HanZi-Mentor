from django.db import models


class Caracter(models.Model):
    """Un hanzi con su información de escritura y significado."""

    hanzi = models.CharField(max_length=4, unique=True, db_index=True)
    pinyin = models.CharField(max_length=64, blank=True)
    definicion = models.TextField(blank=True)
    radical = models.CharField(max_length=4, blank=True)
    descomposicion = models.CharField(max_length=64, blank=True)

    nivel_hsk = models.PositiveSmallIntegerField(
        null=True, blank=True, db_index=True,
        help_text="Nivel HSK. Null si el carácter no está en ninguna lista oficial.",
    )
    frecuencia = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Posición en listas de frecuencia. Menor = más común.",
    )

    class Meta:
        ordering = ["nivel_hsk", "frecuencia", "hanzi"]

    def total_trazos(self):
        return self.trazos.count()

    def __str__(self):
        return f"{self.hanzi} ({self.pinyin})"


class Trazo(models.Model):
    """Un trazo individual, en su posición dentro del orden de escritura."""

    caracter = models.ForeignKey(
        Caracter, related_name="trazos", on_delete=models.CASCADE
    )
    secuencia = models.PositiveSmallIntegerField(
        help_text="Orden de escritura, empezando en 1."
    )
    path_svg = models.TextField(
        help_text="Contorno del trazo. Sistema de 1024x1024 con eje Y invertido."
    )
    mediana = models.JSONField(
        default=list,
        help_text="Puntos de la línea central. Se compara contra el trazo del usuario.",
    )

    class Meta:
        ordering = ["secuencia"]
        unique_together = [("caracter", "secuencia")]

    def __str__(self):
        return f"{self.caracter.hanzi} · trazo {self.secuencia}"
