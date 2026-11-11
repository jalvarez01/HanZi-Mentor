"""Códigos de error que acepta `codigo_error` al responder un ejercicio (RF-IA-01).

Es la misma lista que progreso-flask (dominio/codigos.py): los doce
`explicacion.codigo` de evaluacion-flask (adaptadores/reglas.py) y los dos
de Práctica, donde no hay evaluación del servicio. Un servicio no importa
código de otro, así que la lista se copia y tests/test_codigos.py la
compara con los otros dos servicios.

Se valida acá, antes de guardar la respuesta: si solo la validara
progreso-flask, su 400 llegaría al estudiante como "el servicio de progreso
no respondió".
"""

CODIGOS_EVALUACION = (
    "TRAZO_FUERA_DE_LUGAR",
    "TRAZO_INVERTIDO",
    "TRAZO_INCOMPLETO",
    "TRAZO_CORTO",
    "TRAZO_LARGO",
    "TRAZO_IMPRECISO",
    "PINYIN_INICIAL",
    "PINYIN_FINAL",
    "PINYIN_DISTINTO",
    "SIGNIFICADO_PARCIAL",
    "SIGNIFICADO_CERCANO",
    "SIGNIFICADO_DISTINTO",
)

# "Fallé" en un ejercicio de trazo y "No lo sé" en uno de pinyin.
CODIGOS_PRACTICA = ("TRAZO_AUTOCALIFICADO", "NO_SABE")

CODIGOS_ERROR = frozenset(CODIGOS_EVALUACION + CODIGOS_PRACTICA)
