"""
Ejercicios adaptativos (RF-IA-03): a partir de un patrón de error que
detectó progreso-flask (RF-IA-01), el tutor arma ejercicios dirigidos a esa
debilidad.

Funciones puras: reciben el patrón tal como lo devuelve
GET /api/v2/progreso/<id>/patrones/ ({codigo, caracteres, ...}) y devuelven
qué practicar. No leen ni guardan nada.

Cada patrón se ataca con el tipo de ejercicio que lo trabaja:

| Patrón                                             | Ejercicio     |
|----------------------------------------------------|---------------|
| PATRON_TRAZO_INVERTIDO, _LONGITUD, _POSICION, _FORMA | trazo       |
| PATRON_PINYIN_INICIAL, _FINAL, _LECTURA, PATRON_NO_SABE | pinyin   |
| PATRON_SIGNIFICADO                                 | significado   |
| PATRON_CARACTER_RECURRENTE                         | trazo         |
| PATRON_RETROCESO                                   | pinyin        |

Los caracteres son los del patrón, en su orden (el más fallado primero). Un
carácter recurrente se trabaja con su escritura, como sugiere el consejo de
ese patrón (practicarlo en Trazos), y uno que ya se dominaba y se olvidó, con
su lectura, que es lo primero que se pierde.

La dificultad baja un punto (mínimo 1): es la debilidad del estudiante, así
que el ejercicio dirigido empieza un paso más fácil que el resto de la
sesión. Un patrón desconocido no genera nada.
"""

from dataclasses import dataclass

TIPO_POR_PATRON = {
    "PATRON_TRAZO_INVERTIDO": "trazo",
    "PATRON_TRAZO_LONGITUD": "trazo",
    "PATRON_TRAZO_POSICION": "trazo",
    "PATRON_TRAZO_FORMA": "trazo",
    "PATRON_PINYIN_INICIAL": "pinyin",
    "PATRON_PINYIN_FINAL": "pinyin",
    "PATRON_PINYIN_LECTURA": "pinyin",
    "PATRON_NO_SABE": "pinyin",
    "PATRON_SIGNIFICADO": "significado",
    "PATRON_CARACTER_RECURRENTE": "trazo",
    "PATRON_RETROCESO": "pinyin",
}

DIFICULTAD_MINIMA = 1


@dataclass(frozen=True)
class EjercicioAdaptado:
    caracter: str
    tipo: str
    dificultad: int
    patron: str


def dificultad_adaptada(dificultad):
    """Un punto menos que la sesión, sin bajar de 1."""
    return max(DIFICULTAD_MINIMA, int(dificultad or DIFICULTAD_MINIMA) - 1)


def generar_ejercicio_adaptado(patron, dificultad, cantidad, excluir=()):
    """generarEjercicioAdaptado(p) de RF-IA-03 para un patrón.

    patron: {codigo, caracteres, ...} de progreso-flask.
    Devuelve hasta `cantidad` EjercicioAdaptado, sin los caracteres de
    `excluir` ni repetidos. Un patrón sin tipo conocido o mal formado da [].
    """
    if not isinstance(patron, dict) or cantidad <= 0:
        return []
    codigo = patron.get("codigo")
    tipo = TIPO_POR_PATRON.get(codigo)
    caracteres = patron.get("caracteres")
    if tipo is None or not isinstance(caracteres, list):
        return []

    vistos = set(excluir)
    ejercicios = []
    for caracter in caracteres:
        if not isinstance(caracter, str) or not caracter or caracter in vistos:
            continue
        vistos.add(caracter)
        ejercicios.append(EjercicioAdaptado(caracter, tipo, dificultad_adaptada(dificultad), codigo))
        if len(ejercicios) == cantidad:
            break
    return ejercicios


def adaptar_a_patrones(patrones, dificultad, cantidad, excluir=(), generar=generar_ejercicio_adaptado):
    """Ejercicios dirigidos para la sesión, del patrón más relevante al menos.

    progreso-flask ya devuelve los patrones ordenados por relevancia: se
    toman ejercicios del primero y, si no alcanza para `cantidad`, de los
    siguientes. Un carácter aparece una sola vez, con el patrón más
    relevante que lo nombra.
    """
    ejercicios = []
    usados = set(excluir)
    for patron in patrones or []:
        faltan = cantidad - len(ejercicios)
        if faltan <= 0:
            break
        nuevos = generar(patron, dificultad, faltan, excluir=usados)
        ejercicios.extend(nuevos)
        usados.update(e.caracter for e in nuevos)
    return ejercicios
