"""
Detección de patrones de error (RF-IA-01): a partir del historial reciente
de fallos, dice en qué se equivoca seguido el estudiante.

Función pura: recibe el historial (la lista que guarda
ProgresoUsuario.historial_errores) y el momento actual, y devuelve los
patrones ordenados por relevancia. No lee ni guarda nada.

Dos clases de patrón:
- tipo "error": un mismo tipo de error se repite (trazos al revés, la
  consonante inicial del pinyin...). Cuentan los fallos de sesión y los de
  la página Trazos.
- tipo "caracter": el problema es un carácter, no un tipo de error. Solo
  cuentan los fallos de sesión: en Trazos hay un fallo por trazo, no por
  ejercicio, y un carácter de muchos trazos inflaría la cuenta.

Umbrales:
- VENTANA_DIAS = 14. Un carácter fallado vuelve a aparecer entre 12 horas y
  7 días después, así que una debilidad real se repite dentro de la
  ventana, y una ya corregida deja de aparecer a las dos semanas.
- MIN_OCURRENCIAS = 3. Un fallo es un descuido y dos pueden ser
  coincidencia.
- PROPORCION_MINIMA = 0.30, solo en los patrones de tipo "error": las
  ocurrencias del patrón sobre los fallos de su misma familia (trazo,
  pinyin o significado) en la ventana. Supera el 25 % que daría un reparto
  parejo entre los cuatro patrones de una familia. Se mide contra la
  familia para que mucha práctica de trazos no esconda un patrón de pinyin.
  En los de tipo "caracter" no aplica: la cuenta ya es por carácter.

Los textos van en español con N_ y se traducen al responder
(serializacion.py): un título corto y un consejo con una sola idea.

PATRON_SIGNIFICADO está definido y probado, pero hoy no puede aparecer:
Práctica evalúa como pinyin los ejercicios que no son de trazo, así que
ningún código SIGNIFICADO_* llega al historial.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from mensajes import N_

from .codigos import NO_SABE, ORIGEN_SESION

VENTANA_DIAS = 14
MIN_OCURRENCIAS = 3
PROPORCION_MINIMA = 0.30
# Cuántos caracteres se listan en cada patrón.
MAX_CARACTERES = 5

TIPO_ERROR = "error"
TIPO_CARACTER = "caracter"


@dataclass(frozen=True)
class Patron:
    codigo: str
    tipo: str
    frecuencia: int
    caracteres: tuple
    ultima_vez: datetime
    titulo: str
    consejo: str


# familia -> patrón -> (códigos de error que lo alimentan, título, consejo)
PATRONES_DE_ERROR = {
    "trazo": {
        "PATRON_TRAZO_INVERTIDO": (
            ("TRAZO_INVERTIDO",),
            N_("Trazos al revés"),
            N_(
                "Antes de trazar, mirá dónde empieza el modelo: casi siempre es "
                "de arriba hacia abajo y de izquierda a derecha."
            ),
        ),
        "PATRON_TRAZO_LONGITUD": (
            ("TRAZO_CORTO", "TRAZO_LARGO", "TRAZO_INCOMPLETO"),
            N_("Largo del trazo"),
            N_("Seguí el modelo hasta la punta y levantá el dedo recién ahí."),
        ),
        "PATRON_TRAZO_POSICION": (
            ("TRAZO_FUERA_DE_LUGAR",),
            N_("Trazos fuera de lugar"),
            N_("Usá la cruz punteada para ubicar dónde empieza cada trazo."),
        ),
        "PATRON_TRAZO_FORMA": (
            ("TRAZO_IMPRECISO",),
            N_("Forma del trazo"),
            N_("Trazá más despacio y seguí la guía de punta a punta."),
        ),
    },
    "pinyin": {
        "PATRON_PINYIN_INICIAL": (
            ("PINYIN_INICIAL",),
            N_("Primer sonido del pinyin"),
            N_("Decí la sílaba en voz alta y prestá atención a cómo empieza."),
        ),
        "PATRON_PINYIN_FINAL": (
            ("PINYIN_FINAL",),
            N_("Terminación del pinyin"),
            N_("Decí la sílaba en voz alta y prestá atención a cómo termina."),
        ),
        "PATRON_PINYIN_LECTURA": (
            ("PINYIN_DISTINTO",),
            N_("Lecturas confundidas"),
            N_("Leé estos caracteres en voz alta antes de tu próxima sesión."),
        ),
        "PATRON_NO_SABE": (
            (NO_SABE,),
            N_("Caracteres que todavía no conocés"),
            N_("Mirá primero su ficha en Trazos y después volvé a practicarlos."),
        ),
    },
    "significado": {
        "PATRON_SIGNIFICADO": (
            ("SIGNIFICADO_PARCIAL", "SIGNIFICADO_CERCANO", "SIGNIFICADO_DISTINTO"),
            N_("Significados"),
            N_("Asociá cada carácter con una sola palabra y respondé con esa."),
        ),
    },
}

CARACTER_RECURRENTE = (
    "PATRON_CARACTER_RECURRENTE",
    N_("Caracteres que se repiten en tus fallos"),
    N_("Practicalos en Trazos antes de tu próxima sesión."),
)
RETROCESO = (
    "PATRON_RETROCESO",
    N_("Caracteres que ya dominabas"),
    N_("Volvé a repasarlos: lo que no se practica seguido se olvida."),
)


def _fecha(valor):
    """La fecha ISO del historial como datetime en UTC, o None si no sirve."""
    if not isinstance(valor, str):
        return None
    try:
        fecha = datetime.fromisoformat(valor)
    except ValueError:
        return None
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc)


def _fallos_en_ventana(historial, momento, ventana_dias):
    """Entradas válidas del historial dentro de la ventana, con la fecha ya leída.

    El historial es JSON: una entrada mal formada se ignora en vez de romper.
    """
    desde = momento - timedelta(days=ventana_dias)
    fallos = []
    for entrada in historial or []:
        if not isinstance(entrada, dict):
            continue
        caracter = entrada.get("caracter")
        fecha = _fecha(entrada.get("fecha"))
        if not isinstance(caracter, str) or not caracter or fecha is None or fecha < desde:
            continue
        codigo = entrada.get("codigo")
        fallos.append({
            # Un código que no es texto cuenta como fallo sin código.
            "codigo": codigo if isinstance(codigo, str) else None,
            "caracter": caracter,
            "fecha": fecha,
            "origen": entrada.get("origen", ORIGEN_SESION),
            "dominado": entrada.get("dominado") is True,
        })
    return fallos


def _caracteres(fallos):
    """Los caracteres de esos fallos, del más fallado al menos fallado."""
    veces = Counter(f["caracter"] for f in fallos)
    ultima = {}
    for f in fallos:
        ultima[f["caracter"]] = max(ultima.get(f["caracter"], f["fecha"]), f["fecha"])
    ordenados = sorted(veces, key=lambda c: (-veces[c], -ultima[c].timestamp(), c))
    return tuple(ordenados[:MAX_CARACTERES])


def _patron(codigo, tipo, titulo, consejo, fallos):
    return Patron(
        codigo=codigo,
        tipo=tipo,
        frecuencia=len(fallos),
        caracteres=_caracteres(fallos),
        ultima_vez=max(f["fecha"] for f in fallos),
        titulo=titulo,
        consejo=consejo,
    )


def _por_tipo_de_error(fallos):
    patrones = []
    for definiciones in PATRONES_DE_ERROR.values():
        de_la_familia = {c for codigos, _, _ in definiciones.values() for c in codigos}
        total = sum(1 for f in fallos if f["codigo"] in de_la_familia)
        for codigo, (codigos, titulo, consejo) in definiciones.items():
            ocurrencias = [f for f in fallos if f["codigo"] in codigos]
            if len(ocurrencias) < MIN_OCURRENCIAS:
                continue
            if len(ocurrencias) / total < PROPORCION_MINIMA:
                continue
            patrones.append(_patron(codigo, TIPO_ERROR, titulo, consejo, ocurrencias))
    return patrones


def _por_caracter(fallos):
    de_sesion = [f for f in fallos if f["origen"] == ORIGEN_SESION]
    patrones = []

    veces = Counter(f["caracter"] for f in de_sesion)
    recurrentes = [f for f in de_sesion if veces[f["caracter"]] >= MIN_OCURRENCIAS]
    if recurrentes:
        codigo, titulo, consejo = CARACTER_RECURRENTE
        patrones.append(_patron(codigo, TIPO_CARACTER, titulo, consejo, recurrentes))

    retrocesos = [f for f in de_sesion if f["dominado"]]
    if len(retrocesos) >= MIN_OCURRENCIAS:
        codigo, titulo, consejo = RETROCESO
        patrones.append(_patron(codigo, TIPO_CARACTER, titulo, consejo, retrocesos))

    return patrones


def detectar_patron_error(historial, momento, ventana_dias=VENTANA_DIAS):
    """Patrones de error del estudiante, del más relevante al menos relevante.

    historial: lista de {codigo, caracter, fecha, origen, dominado}.
    momento: fecha actual (con zona); la ventana termina acá.

    El orden es por frecuencia, después por el más reciente y después por
    código, para que la misma entrada dé siempre la misma lista.
    """
    fallos = _fallos_en_ventana(historial, momento, ventana_dias)
    patrones = _por_tipo_de_error(fallos) + _por_caracter(fallos)
    return sorted(
        patrones,
        key=lambda p: (-p.frecuencia, -p.ultima_vez.timestamp(), p.codigo),
    )
