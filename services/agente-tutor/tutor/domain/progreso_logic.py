"""
Reglas de progreso del usuario — qué pasa con el estado de dominio de un
carácter cuando se acierta o se falla.

Vive separado de progreso.models.ProgresoUsuario para que el modelo no
tenga más responsabilidad que persistir: estas funciones reciben la
entidad, la mutan en memoria y quien las llama decide cuándo guardar.
Mismo enfoque que domain/repaso.py: funciones puras sobre datos, no
métodos del modelo.
"""

NIVEL_HSK_MAXIMO = 6


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


def desbloquear_siguiente_nivel(progreso, tope=NIVEL_HSK_MAXIMO):
    if progreso.nivel_max_desbloqueado < tope:
        progreso.nivel_max_desbloqueado += 1
