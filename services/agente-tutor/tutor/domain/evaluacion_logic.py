"""
Reglas de evaluación de respuestas — decide si una respuesta es correcta
según el tipo de ejercicio (trazo, pinyin, significado) y su dificultad.

Mismo enfoque que progreso_logic.py: funciones puras, sin Django, sin
requests, sin acceso a BD. Quien llama resuelve datos_correctos (por HTTP,
por BD, o como sea) antes de invocar estas funciones.
"""

import unicodedata
from difflib import SequenceMatcher

UMBRALES_SIGNIFICADO = {
    1: 0.55,
    2: 0.65,
    3: 0.75,
    4: 0.85,
    5: 0.92,
}


def _normalizar_texto(texto: str) -> str:
    return " ".join((texto or "").strip().lower().split())


def _sin_diacriticos(texto: str) -> str:
    """Quita tildes/tonos: "xué" -> "xue". Deja intacto el resto del texto."""
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def _evaluar_pinyin(respuesta_usuario: str, datos_correctos: dict) -> bool:
    esperado = _sin_diacriticos(_normalizar_texto(datos_correctos.get("pinyin", "")))
    recibido = _sin_diacriticos(_normalizar_texto(respuesta_usuario))
    return esperado == recibido


def _evaluar_significado(respuesta_usuario: str, dificultad: int, datos_correctos: dict) -> bool:
    if dificultad not in UMBRALES_SIGNIFICADO:
        raise ValueError(f"Dificultad fuera de rango (1-5): {dificultad}")

    # Compara por conjunto de palabras: el orden no debe penalizar
    # definiciones multi-palabra como "study, learning".
    esperado = _normalizar_texto(datos_correctos.get("definicion", "")).replace(",", " ")
    recibido = _normalizar_texto(respuesta_usuario).replace(",", " ")

    esperado_ordenado = " ".join(sorted(esperado.split()))
    recibido_ordenado = " ".join(sorted(recibido.split()))

    similitud = SequenceMatcher(None, esperado_ordenado, recibido_ordenado).ratio()
    return similitud >= UMBRALES_SIGNIFICADO[dificultad]


def evaluar_respuesta(tipo: str, dificultad: int, respuesta_usuario, datos_correctos: dict) -> bool:
    """Punto de entrada único: aplica la regla de validación según el tipo de ejercicio."""
    if tipo == "pinyin":
        return _evaluar_pinyin(respuesta_usuario, datos_correctos)

    if tipo == "significado":
        return _evaluar_significado(respuesta_usuario, dificultad, datos_correctos)

    if tipo == "trazo":
        # La comparación de trazo no es una regla pura local: depende de la
        # mediana que vive en contenido. Se resuelve en EvaluarEjercicioService
        # vía CatalogoRemoto.comparar_trazo(), no en esta función.
        raise ValueError(
            "La evaluación de 'trazo' no pasa por evaluar_respuesta(); "
            "usa EvaluarEjercicioService, que llama a CatalogoRemoto.comparar_trazo()."
        )

    raise ValueError(f"Tipo de ejercicio desconocido: {tipo}")
