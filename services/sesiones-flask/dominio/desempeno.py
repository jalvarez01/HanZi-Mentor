"""
Desempeño de una sesión de estudio (RF-IA-05): en cuanto la sesión termina,
SesionEstudio.calcular_desempeno() procesa la duración y la fecha y deja
registrados los resultados.

Funciones puras: leen la sesión y sus ejercicios y devuelven un
`Desempeno`. No guardan nada; `registrar_desempeno` solo copia los valores
en las columnas de la sesión y el commit lo hace el servicio.

- La sesión termina con la última respuesta: `completada_en` es esa fecha.
  Las sesiones cerradas antes de RF-IA-05 no la tienen guardada, así que se
  toma la última `respondido_en` de sus ejercicios.
- `duracion_seg` va desde `creada_en` (cuando el estudiante empezó) hasta
  `completada_en`, nunca negativa.
- `dentro_del_tiempo` compara esa duración con `duracion_estimada_min`.
- La tasa es de esta sesión (aciertos / respondidos), con dos decimales, en
  la misma escala de 0 a 1 que la tasa global de progreso-flask.
"""

from dataclasses import dataclass, field

DECIMALES_TASA = 2


@dataclass(frozen=True)
class Desempeno:
    sesion_id: int
    creada_en: object
    completada_en: object
    duracion_seg: int
    duracion_estimada_min: int
    dentro_del_tiempo: bool
    segundos_por_ejercicio: int
    total: int
    aciertos: int
    fallos: int
    tasa_acierto: float
    por_tipo: dict = field(default_factory=dict)


def fecha_de_cierre(sesion):
    """Cuándo terminó la sesión, o None si sigue en curso."""
    if sesion.estado != "completada":
        return None
    if getattr(sesion, "completada_en", None) is not None:
        return sesion.completada_en
    fechas = [e.respondido_en for e in sesion.ejercicios if e.respondido and e.respondido_en]
    return max(fechas) if fechas else None


def duracion_en_segundos(creada_en, completada_en):
    """Segundos enteros entre las dos fechas, sin bajar de 0."""
    return max(0, int((completada_en - creada_en).total_seconds()))


def tasa(aciertos, respondidos):
    if respondidos <= 0:
        return 0.0
    return round(aciertos / respondidos, DECIMALES_TASA)


def calcular_desempeno(sesion):
    """calcularDesempeño() de RF-IA-05. None si la sesión no terminó."""
    completada_en = fecha_de_cierre(sesion)
    if completada_en is None:
        return None

    respondidos = [e for e in sesion.ejercicios if e.respondido]
    aciertos = sum(1 for e in respondidos if e.fue_correcto)
    total = len(respondidos)

    por_tipo = {}
    for e in respondidos:
        grupo = por_tipo.setdefault(e.tipo, {"total": 0, "aciertos": 0})
        grupo["total"] += 1
        grupo["aciertos"] += 1 if e.fue_correcto else 0

    duracion = duracion_en_segundos(sesion.creada_en, completada_en)
    return Desempeno(
        sesion_id=sesion.id,
        creada_en=sesion.creada_en,
        completada_en=completada_en,
        duracion_seg=duracion,
        duracion_estimada_min=sesion.duracion_estimada_min,
        dentro_del_tiempo=duracion <= (sesion.duracion_estimada_min or 0) * 60,
        segundos_por_ejercicio=round(duracion / total) if total else 0,
        total=total,
        aciertos=aciertos,
        fallos=total - aciertos,
        tasa_acierto=tasa(aciertos, total),
        por_tipo=por_tipo,
    )


def registrar_desempeno(sesion, desempeno):
    """Copia en la sesión lo que queda registrado en la base."""
    sesion.completada_en = desempeno.completada_en
    sesion.duracion_seg = desempeno.duracion_seg
    sesion.aciertos = desempeno.aciertos


def resumen(desempenos):
    """Totales de varias sesiones, para el historial."""
    total = sum(d.total for d in desempenos)
    aciertos = sum(d.aciertos for d in desempenos)
    return {
        "sesiones": len(desempenos),
        "ejercicios": total,
        "aciertos": aciertos,
        "tasa_acierto": tasa(aciertos, total),
        "duracion_seg": sum(d.duracion_seg for d in desempenos),
    }
