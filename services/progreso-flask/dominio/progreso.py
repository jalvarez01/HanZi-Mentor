"""
Reglas de progreso del usuario: qué pasa con el estado de dominio de un
carácter cuando se acierta o se falla.

Port de services/agente-tutor/tutor/domain/progreso_logic.py con las mismas
reglas. Las funciones reciben la entidad, la mutan en memoria y nunca
guardan: quien las llama decide cuándo hacer commit.
"""

from datetime import datetime, timedelta

from .codigos import ORIGEN_SESION, ORIGEN_TRAZOS

NIVEL_HSK_MAXIMO = 6

# Fallos que se conservan por origen (sesión y Trazos). Con tope por origen,
# una tarde de práctica en Trazos no saca del historial los fallos de sesión.
HISTORIAL_MAXIMO = 50
# Un reintento del mismo trazo dentro de este tiempo no se vuelve a anotar.
SEGUNDOS_REINTENTO = 120


def racha_de(progreso, caracter):
    return (progreso.aciertos_consecutivos or {}).get(caracter, 0)


def registrar_error(progreso, caracter):
    """Suma un fallo, corta la racha y le quita la condición de dominado."""
    errores = dict(progreso.errores_frecuentes or {})
    errores[caracter] = errores.get(caracter, 0) + 1
    progreso.errores_frecuentes = errores

    rachas = dict(progreso.aciertos_consecutivos or {})
    rachas[caracter] = 0
    progreso.aciertos_consecutivos = rachas

    if caracter in (progreso.caracteres_dominados or []):
        progreso.caracteres_dominados = [
            c for c in progreso.caracteres_dominados if c != caracter
        ]


def registrar_acierto(progreso, caracter):
    """Descuenta un fallo, suma a la racha y marca como dominado si corresponde."""
    errores = dict(progreso.errores_frecuentes or {})

    if caracter in errores:
        errores[caracter] -= 1
        if errores[caracter] <= 0:
            del errores[caracter]
        progreso.errores_frecuentes = errores

    rachas = dict(progreso.aciertos_consecutivos or {})
    rachas[caracter] = rachas.get(caracter, 0) + 1
    progreso.aciertos_consecutivos = rachas

    dominados = list(progreso.caracteres_dominados or [])
    if caracter not in errores and caracter not in dominados:
        dominados.append(caracter)
        progreso.caracteres_dominados = dominados


def registrar_respuesta(progreso, caracter, acerto):
    """Punto de entrada único: aplica la regla de acierto o de error."""
    if acerto:
        registrar_acierto(progreso, caracter)
    else:
        registrar_error(progreso, caracter)


def agendar_repaso(progreso, caracter, cuando):
    """Guarda la fecha del próximo repaso y actualiza la más cercana."""
    agenda = dict(progreso.agenda_repaso or {})
    agenda[caracter] = cuando.isoformat()
    progreso.agenda_repaso = agenda

    if progreso.proximo_repaso is None or cuando < progreso.proximo_repaso:
        progreso.proximo_repaso = cuando


def _es_reintento(historial, caracter, codigo, momento):
    """True si el último fallo igual de Trazos fue hace menos de dos minutos."""
    for entrada in reversed(historial):
        if (
            entrada.get("origen") == ORIGEN_TRAZOS
            and entrada.get("caracter") == caracter
            and entrada.get("codigo") == codigo
        ):
            try:
                anterior = datetime.fromisoformat(entrada.get("fecha"))
            except (TypeError, ValueError):
                return False
            return momento - anterior < timedelta(seconds=SEGUNDOS_REINTENTO)
    return False


def _recortar(historial):
    """Deja los últimos HISTORIAL_MAXIMO fallos de cada origen, en su orden."""
    restantes = {}
    conservados = []
    for entrada in reversed(historial):
        origen = entrada.get("origen")
        if restantes.setdefault(origen, HISTORIAL_MAXIMO) > 0:
            restantes[origen] -= 1
            conservados.append(entrada)
    conservados.reverse()
    return conservados


def anotar_error(progreso, caracter, codigo, momento, origen=ORIGEN_SESION, dominado=False):
    """Guarda un fallo en el historial reciente y lo suma a su código (RF-IA-01).

    codigo: tipo de error, o None si quien responde no lo informó.
    dominado: si el carácter estaba dominado justo antes de fallar.

    En Trazos el mismo trazo se reintenta varias veces seguidas: el mismo
    carácter y código en menos de dos minutos cuenta una sola vez. Devuelve
    False en ese caso, y True si el fallo se anotó.
    """
    historial = list(progreso.historial_errores or [])
    if origen == ORIGEN_TRAZOS and _es_reintento(historial, caracter, codigo, momento):
        return False

    historial.append({
        "codigo": codigo,
        "caracter": caracter,
        "fecha": momento.isoformat(),
        "origen": origen,
        "dominado": bool(dominado),
    })
    progreso.historial_errores = _recortar(historial)

    if codigo:
        totales = dict(progreso.errores_por_codigo or {})
        totales[codigo] = totales.get(codigo, 0) + 1
        progreso.errores_por_codigo = totales
    return True


def desbloquear_siguiente_nivel(progreso, tope=NIVEL_HSK_MAXIMO):
    if progreso.nivel_max_desbloqueado < tope:
        progreso.nivel_max_desbloqueado += 1


def peores_caracteres(errores_frecuentes, limite):
    """Los `limite` caracteres con más fallos, de peor a mejor."""
    ordenados = sorted(
        (errores_frecuentes or {}).items(), key=lambda par: par[1], reverse=True
    )
    return ordenados[:limite]
