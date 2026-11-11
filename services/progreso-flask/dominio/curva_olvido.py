"""
Curva de olvido (RF-IA-02): SM-2 por carácter, con factor de facilidad.

Funciones puras: reciben el estado de un carácter y devuelven el nuevo, sin
leer ni guardar nada. Quien las llama (ProgresoUsuario.actualizar_curva_olvido)
decide cuándo se aplican: una vez por carácter, al cerrar cada sesión.

Estado por carácter (EstadoCurva):
- facilidad: empieza en 2.5 y nunca baja de 1.3;
- repeticiones: aciertos seguidos desde el último fallo;
- intervalo_dias: días hasta el próximo repaso que se agendó.
La fecha del próximo repaso se guarda aparte, en agenda_repaso.

Reglas (SM-2):
- calidad 3 o más (acierto): repeticiones + 1. El intervalo es 1 día en la
  primera repetición, 6 en la segunda y después round(intervalo x facilidad),
  con la facilidad anterior a esta respuesta;
- calidad menor que 3 (fallo): repeticiones 0, intervalo 0 y el próximo
  repaso a las 12 horas, igual que el intervalo corto que ya existía;
- la facilidad se actualiza en toda respuesta, también en un fallo:
  facilidad + 0.1 - (5 - q) x (0.08 + (5 - q) x 0.02). Así un carácter que
  cuesta queda con intervalos más cortos.

El redondeo del intervalo es "la mitad hacia arriba" (17.5 da 18 y 2.5 da
3), no el redondeo bancario de round() de Python.
"""

import math
from dataclasses import dataclass
from datetime import timedelta

from .repaso import INTERVALOS_DIAS

FACILIDAD_INICIAL = 2.5
FACILIDAD_MINIMA = 1.3
PRIMER_INTERVALO_DIAS = 1
SEGUNDO_INTERVALO_DIAS = 6
HORAS_TRAS_FALLO = 12
# Desde esta calidad la respuesta cuenta como acierto.
CALIDAD_APROBADA = 3

# ---------------------------------------------------------- respuesta a calidad

CALIDAD_ACIERTO = 4
# Fallo cercano: recordaba una parte.
CALIDAD_CERCANA = 2
# Fallo, pero lo reconocía; también un fallo sin código.
CALIDAD_FALLO = 1
# No lo recordaba en absoluto.
CALIDAD_NO_SABE = 0

CALIDAD_POR_CODIGO = {
    "PINYIN_INICIAL": CALIDAD_CERCANA,
    "PINYIN_FINAL": CALIDAD_CERCANA,
    "SIGNIFICADO_PARCIAL": CALIDAD_CERCANA,
    "SIGNIFICADO_CERCANO": CALIDAD_CERCANA,
    "PINYIN_DISTINTO": CALIDAD_FALLO,
    "SIGNIFICADO_DISTINTO": CALIDAD_FALLO,
    "TRAZO_AUTOCALIFICADO": CALIDAD_FALLO,
    "NO_SABE": CALIDAD_NO_SABE,
}


def calidad_de_respuesta(acerto, codigo_error=None):
    """Calidad SM-2 (0 a 5) de una respuesta.

    Ninguna respuesta llega a 5: no se mide el tiempo de respuesta ni el
    tono. Un código que no está en la tabla (por ejemplo, un TRAZO_* de la
    página Trazos, que no llega a una sesión) cuenta como fallo sin código.
    """
    if acerto:
        return CALIDAD_ACIERTO
    return CALIDAD_POR_CODIGO.get(codigo_error, CALIDAD_FALLO)


def peor_calidad_por_caracter(respuestas):
    """Carácter -> la peor calidad de sus respuestas en la sesión.

    respuestas: lista de {caracter, acerto, codigo_error}. Un carácter que se
    respondió varias veces se actualiza una sola vez, con su peor respuesta:
    un fallo dice que todavía no está consolidado. Conserva el orden de la
    primera aparición.
    """
    peores = {}
    for r in respuestas:
        calidad = calidad_de_respuesta(r["acerto"], r.get("codigo_error"))
        caracter = r["caracter"]
        peores[caracter] = min(peores.get(caracter, calidad), calidad)
    return peores


# --------------------------------------------------------------------- estado


@dataclass(frozen=True)
class EstadoCurva:
    facilidad: float = FACILIDAD_INICIAL
    repeticiones: int = 0
    intervalo_dias: int = 0

    def a_dict(self):
        return {
            "facilidad": self.facilidad,
            "repeticiones": self.repeticiones,
            "intervalo_dias": self.intervalo_dias,
        }

    @classmethod
    def desde_dict(cls, datos):
        """El estado guardado en JSON, o None si no se puede leer."""
        if not isinstance(datos, dict):
            return None
        try:
            return cls(
                facilidad=max(FACILIDAD_MINIMA, float(datos["facilidad"])),
                repeticiones=max(0, int(datos["repeticiones"])),
                intervalo_dias=max(0, int(datos["intervalo_dias"])),
            )
        except (KeyError, TypeError, ValueError):
            return None


def estado_desde_racha(aciertos_consecutivos):
    """Estado inicial de un carácter que ya tenía repaso con el algoritmo anterior.

    repeticiones = la racha, e intervalo = el que el algoritmo anterior le dio
    a esa racha (1, 3, 7, 16, 35 o 90 días; 0 si la racha es 0). Facilidad
    2.5. Ejemplo: racha 3 da intervalo 7, y el siguiente acierto, 18 días.
    """
    racha = max(0, int(aciertos_consecutivos or 0))
    if racha == 0:
        return EstadoCurva()
    intervalo = INTERVALOS_DIAS[min(racha, len(INTERVALOS_DIAS)) - 1]
    return EstadoCurva(repeticiones=racha, intervalo_dias=intervalo)


# -------------------------------------------------------------------- SM-2


def _redondear(valor):
    return int(math.floor(valor + 0.5))


def nueva_facilidad(facilidad, calidad):
    q = 5 - calidad
    return round(max(FACILIDAD_MINIMA, facilidad + 0.1 - q * (0.08 + q * 0.02)), 4)


def actualizar_curva_olvido(estado, calidad, momento):
    """Aplica una respuesta de calidad 0 a 5 al estado de un carácter.

    Devuelve (estado nuevo, fecha del próximo repaso). `momento` es la
    fecha desde la que se cuenta: el cierre de la sesión.
    """
    if not 0 <= calidad <= 5:
        raise ValueError(f"Calidad fuera de rango (0-5): {calidad}")
    estado = estado or EstadoCurva()
    facilidad = nueva_facilidad(estado.facilidad, calidad)

    if calidad < CALIDAD_APROBADA:
        nuevo = EstadoCurva(facilidad=facilidad, repeticiones=0, intervalo_dias=0)
        return nuevo, momento + timedelta(hours=HORAS_TRAS_FALLO)

    repeticiones = estado.repeticiones + 1
    if repeticiones == 1:
        intervalo = PRIMER_INTERVALO_DIAS
    elif repeticiones == 2:
        intervalo = SEGUNDO_INTERVALO_DIAS
    else:
        # SM-2 clásico: el intervalo usa la facilidad previa a esta respuesta.
        intervalo = max(1, _redondear(estado.intervalo_dias * estado.facilidad))

    nuevo = EstadoCurva(facilidad=facilidad, repeticiones=repeticiones, intervalo_dias=intervalo)
    return nuevo, momento + timedelta(days=intervalo)
