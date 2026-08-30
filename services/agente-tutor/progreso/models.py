from django.db import models


class ProgresoUsuario(models.Model):
    """Estado de aprendizaje de un usuario: qué domina, qué falla, hasta dónde llegó.

    Solo persistencia: las reglas que deciden cómo cambia este estado
    (registrar acierto/error, agendar repaso, desbloquear nivel) viven en
    tutor.domain.progreso_logic, no acá.
    """

    usuario_id = models.UUIDField(unique=True)

    nivel_hsk = models.PositiveSmallIntegerField(
        default=1,
        help_text="Nivel en el que está practicando actualmente.",
    )
    nivel_max_desbloqueado = models.PositiveSmallIntegerField(
        default=1,
        help_text="Nivel más alto al que tiene acceso.",
    )

    tasa_acierto = models.FloatField(
        default=0.5,
        help_text="Proporción de respuestas correctas, de 0.0 a 1.0.",
    )

    caracteres_dominados = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de caracteres que ya no necesitan repaso frecuente.",
    )
    errores_frecuentes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mapa carácter -> número de veces que se falló.",
    )
    aciertos_consecutivos = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mapa carácter -> aciertos seguidos. Alimenta el repaso espaciado.",
    )
    agenda_repaso = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mapa carácter -> fecha ISO del próximo repaso.",
    )

    proximo_repaso = models.DateTimeField(
        null=True,
        blank=True,
        help_text="El más cercano de la agenda. Permite consultar sin abrir el JSON.",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Progreso de usuario"
        verbose_name_plural = "Progresos de usuarios"

    def __str__(self):
        return f"Progreso de {self.usuario_id} — HSK{self.nivel_hsk}"
