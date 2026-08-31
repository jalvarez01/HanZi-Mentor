"""
Comparación de trazos — RF-APR-01.

Compara la trayectoria que dibujó el usuario contra la mediana oficial del
carácter (la línea central del trazo, que viene en los datos de Make Me a
Hanzi).

El problema de fondo: dos personas dibujan el mismo trazo con distinta
velocidad, distinto número de puntos capturados y en un lienzo de distinto
tamaño. Comparar punto a punto los datos crudos no funciona. La solución es
normalizar ambas curvas al mismo sistema de coordenadas y remuestrearlas a
la misma cantidad de puntos repartidos por longitud de arco; recién ahí las
posiciones son comparables.

Este módulo no importa Django ni conoce la base de datos: son funciones
puras sobre listas de puntos, lo que las hace testeables sin migraciones.
"""

import math
from dataclasses import dataclass, field

# Make Me a Hanzi trabaja en un lienzo de 1024x1024 cuyo eje Y crece hacia
# arriba, con el contenido ubicado aproximadamente entre -124 y 900.
LIENZO = 1024
DESPLAZAMIENTO_Y = 900

# Ventana del filtro de suavizado. El dedo produce micro-zigzags que no
# cambian la forma del trazo pero inflan enormemente su longitud medida:
# sin suavizar, un trazo correcto puede reportar 20 veces el recorrido
# esperado. Un promedio móvil de 5 puntos los elimina sin deformar la curva.
VENTANA_SUAVIZADO = 9

# Cantidad de puntos a los que se lleva cada curva antes de compararlas.
# Con menos de 16 se pierden curvas cerradas; por encima de 64 el costo
# sube sin mejorar el veredicto.
PUNTOS_MUESTREO = 32

# Umbrales sobre la distancia media, expresada como fracción del lienzo.
# Calibrados de modo que un trazo hecho con el dedo, con el temblor normal
# de la mano, siga considerándose correcto.
UMBRAL_EXCELENTE = 0.045
UMBRAL_ACEPTABLE = 0.090

# Si el trazo del usuario mide menos del 55% o más del 180% de lo esperado,
# no es el mismo trazo aunque pase cerca de los puntos correctos.
LONGITUD_MINIMA = 0.55
LONGITUD_MAXIMA = 1.80

# Cuánto mejor debe ser la comparación invertida para afirmar que el trazo
# se hizo al revés, y no que simplemente quedó impreciso.
MARGEN_INVERSION = 1.35


@dataclass
class ResultadoComparacion:
    """Veredicto sobre un trazo dibujado."""

    aprobado: bool
    puntaje: int                      # 0 a 100
    motivo: str                       # correcto | invertido | impreciso | incompleto | vacio
    distancia_media: float            # fracción del lienzo
    razon_longitud: float             # largo del usuario / largo esperado
    invertido: bool = False
    detalle: str = ""
    puntos_lejanos: list = field(default_factory=list)

    def a_dict(self):
        return {
            "aprobado": self.aprobado,
            "puntaje": self.puntaje,
            "motivo": self.motivo,
            "invertido": self.invertido,
            "detalle": self.detalle,
            "distancia_media": round(self.distancia_media, 4),
            "razon_longitud": round(self.razon_longitud, 3),
            "puntos_lejanos": self.puntos_lejanos,
        }


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------


def normalizar_puntos(puntos, ancho, alto):
    """
    Lleva los puntos del lienzo del navegador al sistema de Make Me a Hanzi.

    El canvas entrega coordenadas en píxeles con el origen arriba a la
    izquierda y el eje Y creciendo hacia abajo. El dataset usa un lienzo de
    1024 con el eje Y invertido, así que hay que escalar y reflejar.
    """
    if not puntos or ancho <= 0 or alto <= 0:
        return []

    convertidos = []
    for punto in puntos:
        x, y = _coordenadas(punto)
        convertidos.append((
            x / ancho * LIENZO,
            DESPLAZAMIENTO_Y - (y / alto * LIENZO),
        ))

    return convertidos


def _coordenadas(punto):
    """Acepta tanto [x, y] como {'x': x, 'y': y}."""
    if isinstance(punto, dict):
        return float(punto["x"]), float(punto["y"])
    return float(punto[0]), float(punto[1])


# ---------------------------------------------------------------------------
# Remuestreo por longitud de arco
# ---------------------------------------------------------------------------


def longitud_total(puntos):
    """Suma de las distancias entre puntos consecutivos."""
    return sum(
        _distancia(puntos[i], puntos[i + 1])
        for i in range(len(puntos) - 1)
    )


def remuestrear(puntos, cantidad=PUNTOS_MUESTREO):
    """
    Devuelve `cantidad` puntos repartidos uniformemente sobre la curva.

    Así dejan de importar la velocidad del trazo ni cuántos puntos capturó
    el navegador: dos curvas con la misma forma producen la misma muestra.
    """
    # Trabajamos siempre con tuplas para que la salida sea homogénea,
    # sin importar si la entrada vino como listas o como tuplas.
    puntos = [(float(p[0]), float(p[1])) for p in puntos]

    if len(puntos) < 2:
        return puntos * cantidad if puntos else []

    total = longitud_total(puntos)
    if total == 0:
        return [puntos[0]] * cantidad

    paso = total / (cantidad - 1)
    resultado = [puntos[0]]

    recorrido = 0.0
    indice = 0
    acumulado_en_indice = 0.0

    for n in range(1, cantidad - 1):
        objetivo = n * paso

        # Avanzamos por los segmentos hasta pasar la distancia buscada.
        while indice < len(puntos) - 2:
            largo_segmento = _distancia(puntos[indice], puntos[indice + 1])
            if acumulado_en_indice + largo_segmento >= objetivo:
                break
            acumulado_en_indice += largo_segmento
            indice += 1

        largo_segmento = _distancia(puntos[indice], puntos[indice + 1])
        if largo_segmento == 0:
            resultado.append(puntos[indice])
            continue

        # Interpolamos dentro del segmento donde cae el objetivo.
        proporcion = (objetivo - acumulado_en_indice) / largo_segmento
        proporcion = max(0.0, min(1.0, proporcion))

        x0, y0 = puntos[indice]
        x1, y1 = puntos[indice + 1]
        resultado.append((
            x0 + (x1 - x0) * proporcion,
            y0 + (y1 - y0) * proporcion,
        ))

    resultado.append(puntos[-1])
    return resultado


def suavizar(puntos, ventana=None):
    """
    Promedio móvil sobre la trayectoria.

    Elimina el temblor de la mano conservando la forma general. Es
    indispensable antes de medir longitudes: los datos crudos de un dedo
    sobre la pantalla tienen decenas de micro-oscilaciones por trazo.
    """
    ventana = ventana or VENTANA_SUAVIZADO

    if len(puntos) <= ventana:
        return list(puntos)

    mitad = ventana // 2
    suavizados = []

    for i in range(len(puntos)):
        desde = max(0, i - mitad)
        hasta = min(len(puntos), i + mitad + 1)
        tramo = puntos[desde:hasta]

        suavizados.append((
            sum(p[0] for p in tramo) / len(tramo),
            sum(p[1] for p in tramo) / len(tramo),
        ))

    return suavizados


def _distancia(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


# ---------------------------------------------------------------------------
# Comparación
# ---------------------------------------------------------------------------


def _distancia_media(muestra_a, muestra_b):
    """Promedio de distancias entre puntos correspondientes, normalizado."""
    if not muestra_a or not muestra_b:
        return float("inf")

    suma = sum(_distancia(p, q) for p, q in zip(muestra_a, muestra_b))
    return (suma / len(muestra_a)) / LIENZO


def comparar_trazo(puntos_usuario, mediana, ancho_lienzo, alto_lienzo):
    """
    Compara el trazo dibujado contra la mediana esperada.

    puntos_usuario: lista de [x, y] en píxeles del canvas.
    mediana: lista de [x, y] del dataset, ya en el sistema de 1024.
    ancho_lienzo / alto_lienzo: tamaño del canvas en píxeles.
    """
    if not mediana or len(mediana) < 2:
        return ResultadoComparacion(
            aprobado=False, puntaje=0, motivo="vacio",
            distancia_media=float("inf"), razon_longitud=0.0,
            detalle="El carácter no tiene datos de trazo para comparar.",
        )

    if not puntos_usuario or len(puntos_usuario) < 2:
        return ResultadoComparacion(
            aprobado=False, puntaje=0, motivo="vacio",
            distancia_media=float("inf"), razon_longitud=0.0,
            detalle="No se registró ningún trazo.",
        )

    esperado = [tuple(map(float, p)) for p in mediana]

    # El suavizado va antes de cualquier medición: sin él, el temblor de la
    # mano hace que un trazo correcto parezca varias veces más largo.
    dibujado = suavizar(
        normalizar_puntos(puntos_usuario, ancho_lienzo, alto_lienzo)
    )

    muestra_esperada = remuestrear(esperado)
    muestra_dibujada = remuestrear(dibujado)

    # La longitud se mide sobre las curvas ya remuestreadas, no sobre los
    # datos crudos. Al repartir 32 puntos por longitud de arco, la poligonal
    # que los une ignora las oscilaciones más finas que ese espaciado, que es
    # justo el ruido que introduce el dedo.
    largo_esperado = longitud_total(muestra_esperada)
    largo_dibujado = longitud_total(muestra_dibujada)
    razon = largo_dibujado / largo_esperado if largo_esperado else 0.0

    directa = _distancia_media(muestra_dibujada, muestra_esperada)
    inversa = _distancia_media(muestra_dibujada, list(reversed(muestra_esperada)))

    # Si al invertir el trazo esperado la coincidencia mejora de forma clara,
    # el usuario recorrió el trazo en sentido contrario.
    invertido = inversa * MARGEN_INVERSION < directa
    distancia = min(directa, inversa) if invertido else directa

    return _dictaminar(distancia, razon, invertido, muestra_dibujada, muestra_esperada)


def _dictaminar(distancia, razon, invertido, muestra_dibujada, muestra_esperada):
    """Traduce las métricas a un veredicto con mensaje para el estudiante."""
    puntaje = _calcular_puntaje(distancia, razon)
    lejanos = _indices_lejanos(muestra_dibujada, muestra_esperada)

    if invertido:
        return ResultadoComparacion(
            aprobado=False, puntaje=min(puntaje, 40), motivo="invertido",
            distancia_media=distancia, razon_longitud=razon, invertido=True,
            detalle=(
                "La forma es correcta, pero lo trazaste en sentido contrario. "
                "Revisá por dónde empieza el trazo."
            ),
            puntos_lejanos=lejanos,
        )

    if razon < LONGITUD_MINIMA:
        return ResultadoComparacion(
            aprobado=False, puntaje=min(puntaje, 45), motivo="incompleto",
            distancia_media=distancia, razon_longitud=razon,
            detalle="El trazo quedó corto. Recorré el trazo completo.",
            puntos_lejanos=lejanos,
        )

    if razon > LONGITUD_MAXIMA:
        return ResultadoComparacion(
            aprobado=False, puntaje=min(puntaje, 45), motivo="incompleto",
            distancia_media=distancia, razon_longitud=razon,
            detalle="El trazo se pasó de largo respecto del esperado.",
            puntos_lejanos=lejanos,
        )

    if distancia <= UMBRAL_EXCELENTE:
        return ResultadoComparacion(
            aprobado=True, puntaje=puntaje, motivo="correcto",
            distancia_media=distancia, razon_longitud=razon,
            detalle="Trazo correcto.",
        )

    if distancia <= UMBRAL_ACEPTABLE:
        return ResultadoComparacion(
            aprobado=True, puntaje=puntaje, motivo="correcto",
            distancia_media=distancia, razon_longitud=razon,
            detalle="Trazo aceptable. Con más precisión quedaría perfecto.",
            puntos_lejanos=lejanos,
        )

    return ResultadoComparacion(
        aprobado=False, puntaje=puntaje, motivo="impreciso",
        distancia_media=distancia, razon_longitud=razon,
        detalle="El trazo se alejó bastante del recorrido esperado.",
        puntos_lejanos=lejanos,
    )


def _calcular_puntaje(distancia, razon):
    """
    Convierte la distancia en una nota de 0 a 100.

    Cae linealmente hasta el umbral aceptable y luego más rápido, para que
    un trazo apenas fuera de rango no reciba el mismo cero que un garabato.
    """
    if distancia == float("inf"):
        return 0

    if distancia <= UMBRAL_ACEPTABLE:
        base = 100 - (distancia / UMBRAL_ACEPTABLE) * 30
    else:
        exceso = (distancia - UMBRAL_ACEPTABLE) / UMBRAL_ACEPTABLE
        base = max(0.0, 70 - exceso * 55)

    # Penalización suave por diferencia de longitud.
    if razon < 1:
        base *= max(0.5, razon) if razon < LONGITUD_MINIMA else 1.0
    elif razon > LONGITUD_MAXIMA:
        base *= 0.6

    return max(0, min(100, round(base)))


def _indices_lejanos(muestra_dibujada, muestra_esperada, tope=3):
    """
    Devuelve dónde se desvió más el trazo, en porcentaje del recorrido.

    Sirve para que la interfaz pueda resaltar el tramo problemático y para
    que el agente tutor explique el error con referencia concreta.
    """
    if not muestra_dibujada or not muestra_esperada:
        return []

    distancias = [
        (i, _distancia(p, q) / LIENZO)
        for i, (p, q) in enumerate(zip(muestra_dibujada, muestra_esperada))
    ]
    distancias.sort(key=lambda par: par[1], reverse=True)

    total = len(muestra_esperada) - 1
    return [
        {
            "posicion": round(i / total, 2),
            "desvio": round(d, 4),
        }
        for i, d in distancias[:tope]
        if d > UMBRAL_ACEPTABLE
    ]
