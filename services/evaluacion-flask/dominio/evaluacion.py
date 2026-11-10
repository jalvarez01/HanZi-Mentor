"""
Reglas de evaluación de respuestas: deciden si una respuesta es correcta
según el tipo de ejercicio (pinyin o significado) y su dificultad.

Port de agente-tutor/tutor/domain/evaluacion_logic.py, con los mismos
umbrales. Funciones puras: sin Flask, sin HTTP y sin base. Quien llama
consigue `datos_correctos` (el detalle del carácter en catalogo-flask) antes
de invocarlas.

Diferencia con v1, a propósito (RF-IA-04): el significado se compara con la
definición completa y también con cada sentido por separado. En v1 un
sentido correcto suelto fallaba ("good" para 好 daba 0.17 contra toda la
definición).

Regla de los sentidos cortos: la respuesta se juzga contra el sentido al
que más se parece. Si ese sentido tiene de 1 a 3 letras ("a", "an", "one"),
solo acierta con coincidencia exacta, tras normalizar (minúsculas, sin
puntuación ni espacios de más); si tiene 4 letras o más, se usa el umbral
de la dificultad. La definición completa también usa el umbral, salvo que
sea un solo sentido corto ("big"). Sin esta regla, "man" y "on" acertaban
para 一 (0.8 contra "an" y "one"; "on" también 0.57 contra "alone").

Limitación: las definiciones del catálogo (Make Me a Hanzi) están en inglés
y no hay traducciones, así que una respuesta en español no acierta.
"""

import re
import unicodedata
from difflib import SequenceMatcher

UMBRALES_SIGNIFICADO = {
    1: 0.55,
    2: 0.65,
    3: 0.75,
    4: 0.85,
    5: 0.92,
}

# Un sentido de hasta estas letras solo acierta con coincidencia exacta.
LETRAS_SENTIDO_CORTO = 3


def _normalizar_texto(texto: str) -> str:
    return " ".join((texto or "").strip().lower().split())


def _sin_diacriticos(texto: str) -> str:
    """Quita tildes y tonos: "xué" -> "xue". Deja intacto el resto del texto."""
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def _lecturas(datos_correctos: dict) -> list:
    """Todas las lecturas del carácter. Un catálogo anterior a `lecturas`
    solo manda `pinyin`, y entonces vale solo esa, como en v1."""
    lecturas = datos_correctos.get("lecturas")
    if isinstance(lecturas, list) and any(isinstance(x, str) and x for x in lecturas):
        return [x for x in lecturas if isinstance(x, str) and x]
    return [datos_correctos.get("pinyin", "")]


def lecturas(datos_correctos: dict) -> list:
    """Lecturas del carácter, con sus marcas de tono (la principal primero)."""
    return _lecturas(datos_correctos)


def lectura_que_coincide(respuesta_usuario: str, datos_correctos: dict) -> str | None:
    """La lectura que coincide con la respuesta, sin contar tonos, o None.

    Si varias coinciden (了: "liǎo" y "liào"), gana la que además coincide
    con los tonos escritos; si no, la primera del catálogo.
    """
    escrito = _normalizar_texto(respuesta_usuario)
    recibido = _sin_diacriticos(escrito)
    candidatas = [
        lectura for lectura in _lecturas(datos_correctos)
        if _sin_diacriticos(_normalizar_texto(lectura)) == recibido
    ]
    for lectura in candidatas:
        if _normalizar_texto(lectura) == escrito:
            return lectura
    return candidatas[0] if candidatas else None


def _evaluar_pinyin(respuesta_usuario: str, datos_correctos: dict) -> bool:
    # Cualquier lectura vale: 长 se acepta como "cháng" o como "zhǎng".
    return lectura_que_coincide(respuesta_usuario, datos_correctos) is not None


def sentidos(definicion: str) -> list:
    """Sentidos de una definición: "good, fine; well" -> ["good", "fine", "well"]."""
    partes = (_normalizar_texto(p) for p in re.split(r"[;,]", definicion or ""))
    return [p for p in partes if p]


def _palabras_ordenadas(texto: str) -> str:
    # Compara por conjunto de palabras: el orden no debe penalizar
    # definiciones de varias palabras como "study, learning".
    return " ".join(sorted(_normalizar_texto(texto).replace(",", " ").split()))


def _sin_puntuacion(texto: str) -> str:
    return _normalizar_texto(re.sub(r"[^\w\s]", " ", texto or ""))


def es_sentido_corto(texto: str) -> bool:
    """1 a 3 letras: solo vale la coincidencia exacta."""
    return len(re.sub(r"[\W\d_]", "", texto or "")) <= LETRAS_SENTIDO_CORTO


def _similitud(texto: str, respuesta_usuario: str) -> float:
    return SequenceMatcher(None, _palabras_ordenadas(texto), _palabras_ordenadas(respuesta_usuario)).ratio()


def _coincide_exacto(texto: str, respuesta_usuario: str) -> bool:
    return _sin_puntuacion(texto) == _sin_puntuacion(respuesta_usuario)


def sentido_mas_parecido(respuesta_usuario: str, definicion: str) -> str:
    """El sentido más parecido a la respuesta (o la definición, si no se
    puede separar). Ante un empate gana el primero del catálogo."""
    return max(
        sentidos(definicion) or [definicion or ""],
        key=lambda s: _similitud(s, respuesta_usuario),
    )


def similitud_significado(respuesta_usuario: str, definicion: str) -> float:
    """Similitud (0 a 1) que decide el acierto, con la regla de los
    sentidos cortos (ver el docstring del módulo).

    Un sentido corto da 1.0 si coincide exacto y no cuenta si no.
    """
    def valor(texto):
        if es_sentido_corto(texto):
            return 1.0 if _coincide_exacto(texto, respuesta_usuario) else 0.0
        return _similitud(texto, respuesta_usuario)

    return max(
        valor(definicion or ""),
        valor(sentido_mas_parecido(respuesta_usuario, definicion)),
    )


def umbral_significado(dificultad: int) -> float:
    if dificultad not in UMBRALES_SIGNIFICADO:
        raise ValueError(f"Dificultad fuera de rango (1-5): {dificultad}")
    return UMBRALES_SIGNIFICADO[dificultad]


def _evaluar_significado(respuesta_usuario: str, dificultad: int, datos_correctos: dict) -> bool:
    umbral = umbral_significado(dificultad)
    similitud = similitud_significado(respuesta_usuario, datos_correctos.get("definicion", ""))
    return similitud >= umbral


def evaluar_respuesta(tipo: str, dificultad: int, respuesta_usuario, datos_correctos: dict) -> bool:
    """Punto de entrada único: aplica la regla de validación según el tipo de ejercicio."""
    if tipo == "pinyin":
        return _evaluar_pinyin(respuesta_usuario, datos_correctos)

    if tipo == "significado":
        return _evaluar_significado(respuesta_usuario, dificultad, datos_correctos)

    if tipo == "trazo":
        # El trazo no es una regla pura local: necesita la mediana del
        # catálogo y la comparación de trazos-flask. Lo resuelve
        # EvaluacionService por HTTP, no esta función.
        raise ValueError(
            "La evaluación de 'trazo' no pasa por evaluar_respuesta(); "
            "usa EvaluacionService, que llama a trazos-flask."
        )

    raise ValueError(f"Tipo de ejercicio desconocido: {tipo}")
