"""
Patrón Builder: construcción paso a paso de una sesión de estudio.

Port de agente-tutor/tutor/domain/builders.py con las mismas validaciones.
Regla central: nada se guarda hasta que build() verifique todas las
invariantes. Si algo falta, lanza SesionInvalidaError en vez de persistir
una sesión a medias.

En Django build() guardaba con el ORM dentro de transaction.atomic. Acá
recibe un `repositorio` con `guardar_sesion(datos, ejercicios)`, que guarda
la sesión y sus ejercicios en una sola transacción. Así el Builder no
depende de SQLAlchemy.
"""

from mensajes import N_

from .excepciones import NivelNoPermitidoError, SesionInvalidaError

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
            raise SesionInvalidaError(N_("La sesión requiere un usuario."))

        if self._nivel_hsk not in NIVELES_VALIDOS:
            raise SesionInvalidaError(N_("Nivel HSK inválido: %(nivel)s."), nivel=self._nivel_hsk)

        if self._nivel_hsk > self._nivel_max_desbloqueado:
            raise NivelNoPermitidoError(
                N_("HSK%(nivel)s aún no está desbloqueado (máximo actual: HSK%(maximo)s)."),
                nivel=self._nivel_hsk,
                maximo=self._nivel_max_desbloqueado,
            )

        if self._dificultad is None:
            raise SesionInvalidaError(N_("La sesión requiere una dificultad."))

        if len(self._ejercicios) < MIN_EJERCICIOS:
            raise SesionInvalidaError(
                N_("Una sesión necesita al menos %(minimo)s ejercicios."), minimo=MIN_EJERCICIOS
            )

        if len(self._ejercicios) > MAX_EJERCICIOS:
            raise SesionInvalidaError(
                N_("Una sesión no puede exceder %(maximo)s ejercicios."), maximo=MAX_EJERCICIOS
            )

    # ---------- construcción final ----------

    def build(self, repositorio):
        """Valida primero; solo entonces guarda sesión y ejercicios juntos."""
        self._validar()

        datos = {
            "usuario_id": self._usuario_id,
            "nivel_hsk": self._nivel_hsk,
            "dificultad": self._dificultad,
            "duracion_estimada_min": self._duracion,
            "estado": "activa",
        }
        return repositorio.guardar_sesion(datos, [dict(e) for e in self._ejercicios])
