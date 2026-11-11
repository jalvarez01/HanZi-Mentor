"""Códigos de error que acepta el progreso (RF-IA-01).

Los doce primeros son los `explicacion.codigo` de evaluacion-flask
(adaptadores/reglas.py, RF-IA-04). Un servicio no importa código de otro,
así que la lista se copia: tests/test_codigos.py la compara con ese archivo
y sesiones-flask tiene la misma copia en dominio/codigos_error.py.

Los dos últimos nacen en Práctica, donde no hay evaluación del servicio:
- TRAZO_AUTOCALIFICADO: el estudiante marcó "Fallé" en un ejercicio de trazo;
- NO_SABE: respondió "No lo sé" en un ejercicio de pinyin.
"""

CODIGOS_TRAZO = (
    "TRAZO_FUERA_DE_LUGAR",
    "TRAZO_INVERTIDO",
    "TRAZO_INCOMPLETO",
    "TRAZO_CORTO",
    "TRAZO_LARGO",
    "TRAZO_IMPRECISO",
)
CODIGOS_PINYIN = ("PINYIN_INICIAL", "PINYIN_FINAL", "PINYIN_DISTINTO")
CODIGOS_SIGNIFICADO = ("SIGNIFICADO_PARCIAL", "SIGNIFICADO_CERCANO", "SIGNIFICADO_DISTINTO")

CODIGOS_EVALUACION = CODIGOS_TRAZO + CODIGOS_PINYIN + CODIGOS_SIGNIFICADO

TRAZO_AUTOCALIFICADO = "TRAZO_AUTOCALIFICADO"
NO_SABE = "NO_SABE"
CODIGOS_PRACTICA = (TRAZO_AUTOCALIFICADO, NO_SABE)

# Lo que acepta POST .../respuestas/ en `codigo_error`.
CODIGOS_ERROR = frozenset(CODIGOS_EVALUACION + CODIGOS_PRACTICA)
# Lo que acepta POST .../errores/ (página Trazos): solo trazos evaluados.
CODIGOS_TRAZO_EVALUADO = frozenset(CODIGOS_TRAZO)

# De dónde viene un fallo del historial.
ORIGEN_SESION = "sesion"   # un ejercicio de una sesión: uno por ejercicio
ORIGEN_TRAZOS = "trazos"   # práctica libre en Trazos: uno por trazo fallado
