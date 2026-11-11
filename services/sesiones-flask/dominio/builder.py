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


def sin_repetir(caracteres, excluir=()):
    """Los caracteres en su orden, sin repetidos y sin los de `excluir`."""
    vistos = set(excluir)
    unicos = []
    for caracter in caracteres or []:
        if caracter not in vistos:
            vistos.add(caracter)
            unicos.append(caracter)
    return unicos


class SesionEstudioBuilder:
    """Fluent Interface: cada método devuelve self para poder encadenar."""

    def __init__(self):
        self._usuario_id = None
        self._nivel_hsk = None
        self._nivel_max_desbloqueado = None
        self._dificultad = None
        self._duracion = 10
        self._ejercicios = []
        # Un carácter aparece una sola vez en la sesión (RF-IA-02): antes un
        # refuerzo podía repetirse como contenido nuevo.
        self._caracteres = set()

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

    def _agregar(self, caracter, tipo, dificultad, es_refuerzo):
        """Agrega un ejercicio, salvo que el carácter ya esté en la sesión."""
        if caracter in self._caracteres:
            return
        self._caracteres.add(caracter)
        self._ejercicios.append(
            {
                "caracter": caracter,
                "tipo": tipo,
                "dificultad": dificultad,
                "es_refuerzo": es_refuerzo,
            }
        )

    def agregar_vencidos(self, caracteres_vencidos):
        """Repasos vencidos de la curva de olvido (RF-IA-02): van primero.

        Tipo `significado` (Práctica lo evalúa como pinyin en el servidor) y
        `es_refuerzo` true, porque es un repaso y no contenido nuevo.
        """
        for caracter in caracteres_vencidos:
            self._agregar(caracter, "significado", self._dificultad or 3, True)
        return self

    def agregar_refuerzos(self, caracteres_fallados):
        """Ejercicios nacidos de errores previos."""
        for caracter in caracteres_fallados:
            self._agregar(caracter, "trazo", self._dificultad or 3, True)
        return self

    def agregar_contenido_nuevo(self, caracteres_nuevos, tipo="significado"):
        for caracter in caracteres_nuevos:
            self._agregar(caracter, tipo, self._dificultad or 2, False)
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
