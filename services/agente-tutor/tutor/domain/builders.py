"""
Patrón Builder — construcción paso a paso de una SesionEstudio.

Regla central: el objeto NUNCA toca la base de datos hasta que build()
verifique todas las invariantes. Si algo falta, lanza SesionInvalidaError
en vez de persistir una sesión a medias.
"""

from django.db import transaction

from ..models import Ejercicio, SesionEstudio
from .exceptions import NivelNoPermitidoError, SesionInvalidaError

MIN_EJERCICIOS = 3
MAX_EJERCICIOS = 20
NIVELES_VALIDOS = range(1, 7)


class SesionEstudioBuilder:
    """Fluent Interface: cada método devuelve self para poder encadenar."""

    def __init__(self):
        self._usuario_id = None
        self._nivel_hsk = None
        self._nivel_max_desbloqueado = None
        self._dificultad = None
        self._duracion = 10
        self._ejercicios = []

    # ---------- pasos de construcción ----------

    def para_usuario(self, usuario_id, nivel_max_desbloqueado):
        self._usuario_id = usuario_id
        self._nivel_max_desbloqueado = nivel_max_desbloqueado
        return self

    def en_nivel(self, nivel_hsk):
        self._nivel_hsk = nivel_hsk
        return self

    def con_dificultad(self, dificultad):
        self._dificultad = max(1, min(5, dificultad))
        return self

    def con_duracion(self, minutos):
        self._duracion = minutos
        return self

    def agregar_refuerzos(self, caracteres_fallados):
        """Ejercicios nacidos de errores previos: máxima prioridad."""
        for caracter in caracteres_fallados:
            self._ejercicios.append(
                {
                    "caracter": caracter,
                    "tipo": "trazo",
                    "dificultad": self._dificultad or 3,
                    "es_refuerzo": True,
                }
            )
        return self

    def agregar_contenido_nuevo(self, caracteres_nuevos, tipo="significado"):
        for caracter in caracteres_nuevos:
            self._ejercicios.append(
                {
                    "caracter": caracter,
                    "tipo": tipo,
                    "dificultad": self._dificultad or 2,
                    "es_refuerzo": False,
                }
            )
        return self

    # ---------- validación ----------

    def _validar(self):
        if not self._usuario_id:
            raise SesionInvalidaError("La sesión requiere un usuario.")

        if self._nivel_hsk not in NIVELES_VALIDOS:
            raise SesionInvalidaError(f"Nivel HSK inválido: {self._nivel_hsk}.")

        if self._nivel_hsk > self._nivel_max_desbloqueado:
            raise NivelNoPermitidoError(
                f"HSK{self._nivel_hsk} aún no está desbloqueado "
                f"(máximo actual: HSK{self._nivel_max_desbloqueado})."
            )

        if self._dificultad is None:
            raise SesionInvalidaError("La sesión requiere una dificultad.")

        if len(self._ejercicios) < MIN_EJERCICIOS:
            raise SesionInvalidaError(
                f"Una sesión necesita al menos {MIN_EJERCICIOS} ejercicios."
            )

        if len(self._ejercicios) > MAX_EJERCICIOS:
            raise SesionInvalidaError(
                f"Una sesión no puede exceder {MAX_EJERCICIOS} ejercicios."
            )

    # ---------- construcción final ----------

    @transaction.atomic
    def build(self):
        """Valida primero; solo entonces persiste sesión + ejercicios."""
        self._validar()

        sesion = SesionEstudio.objects.create(
            usuario_id=self._usuario_id,
            nivel_hsk=self._nivel_hsk,
            dificultad=self._dificultad,
            duracion_estimada_min=self._duracion,
            estado="activa",
        )

        Ejercicio.objects.bulk_create(
            [Ejercicio(sesion=sesion, **datos) for datos in self._ejercicios]
        )

        return sesion
