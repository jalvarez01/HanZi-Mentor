from django.db import models


class ProgresoUsuario(models.Model):
    """Estado de aprendizaje de un usuario: qué domina, qué falla, hasta dónde llegó."""

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

    def registrar_error(self, caracter):
        """Suma un fallo, corta la racha y le quita la condicion de dominado."""
        errores = dict(self.errores_frecuentes or {})
        errores[caracter] = errores.get(caracter, 0) + 1
        self.errores_frecuentes = errores

        rachas = dict(self.aciertos_consecutivos or {})
        rachas[caracter] = 0
        self.aciertos_consecutivos = rachas

        if caracter in (self.caracteres_dominados or []):
            self.caracteres_dominados = [
                c for c in self.caracteres_dominados if c != caracter
            ]

    def registrar_acierto(self, caracter):
        """Descuenta un fallo, suma a la racha y marca como dominado si corresponde."""
        errores = dict(self.errores_frecuentes or {})

        if caracter in errores:
            errores[caracter] -= 1
            if errores[caracter] <= 0:
                del errores[caracter]
            self.errores_frecuentes = errores

        rachas = dict(self.aciertos_consecutivos or {})
        rachas[caracter] = rachas.get(caracter, 0) + 1
        self.aciertos_consecutivos = rachas

        dominados = list(self.caracteres_dominados or [])
        if caracter not in errores and caracter not in dominados:
            dominados.append(caracter)
            self.caracteres_dominados = dominados

    def racha_de(self, caracter):
        return (self.aciertos_consecutivos or {}).get(caracter, 0)

    def agendar_repaso(self, caracter, cuando):
        """Guarda la fecha del proximo repaso y actualiza la mas cercana."""
        agenda = dict(self.agenda_repaso or {})
        agenda[caracter] = cuando.isoformat()
        self.agenda_repaso = agenda

        if self.proximo_repaso is None or cuando < self.proximo_repaso:
            self.proximo_repaso = cuando

    def desbloquear_siguiente_nivel(self):
        if self.nivel_max_desbloqueado < 6:
            self.nivel_max_desbloqueado += 1

    def __str__(self):
        return f"Progreso de {self.usuario_id} — HSK{self.nivel_hsk}"
