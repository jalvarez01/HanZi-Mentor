"""Entidades del feedback pedagógico (RF-IA-04): qué recibe el explicador y
qué devuelve.

Los textos van en español, marcados con N_, y se traducen al responder
(serializacion.py). `params` completa sus marcadores con nombre; un valor
`Fragmento` también es un texto marcado con N_ y se traduce antes de
completar la frase.
"""

from dataclasses import dataclass, field


class Fragmento(str):
    """Parte de una frase que también se traduce: "hacia abajo", "al final"."""


@dataclass(frozen=True)
class ErrorEvaluado:
    """Veredicto de una respuesta y el contexto para explicarlo.

    `respuesta` es el texto del usuario (pinyin, significado) o su trazo.
    `datos_correctos` es el detalle del carácter en catalogo-flask. Para
    trazo, `veredicto_trazo` es la respuesta de trazos-flask y `secuencia`
    el número del trazo.
    """

    acerto: bool
    caracter: str
    respuesta: object
    datos_correctos: dict
    dificultad: int = 3
    secuencia: int | None = None
    veredicto_trazo: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Explicacion:
    """Por qué falló la respuesta y qué hacer en el siguiente intento.

    `codigo` es estable: lo usan el frontend y las pruebas, no cambia con el
    idioma ni con la redacción.
    """

    codigo: str
    titulo: str
    porque: str
    pista: str
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Nota:
    """Dato extra sobre una respuesta correcta (por ejemplo, su tono)."""

    codigo: str
    texto: str
    params: dict = field(default_factory=dict)
