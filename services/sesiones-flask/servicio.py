"""
Casos de uso: crear una sesión adaptativa y responder un ejercicio.

Port de SesionEstudioService y ResponderEjercicioService de
agente-tutor/tutor/services.py. La diferencia es que el progreso ya no es
una tabla local: se lee y se registra en progreso-flask por HTTP
(clientes.ProgresoRemoto), y los caracteres nuevos vienen de catalogo-flask.
"""

from dominio import sesion as reglas
from dominio.adaptacion import adaptar_a_patrones
from dominio.builder import SesionEstudioBuilder, sin_repetir
from dominio.desempeno import registrar_desempeno, resumen
from dominio.excepciones import (
    EjercicioNoEncontradoError,
    EjercicioYaRespondidoError,
    SesionNoCompletadaError,
    SesionNoEncontradaError,
)
from dominio.repaso import calcular_proximo_repaso, racha_previa
from mensajes import N_
from modelos import ahora
from repositorio import SesionesRepositorio

# Composición de una sesión: primero hasta 4 repasos vencidos (RF-IA-02),
# después hasta 3 ejercicios adaptados a los patrones de error (RF-IA-03),
# hasta 3 refuerzos y los nuevos completan 7, con al menos 1 nuevo. Como
# mucho 4 + 3 + 3 + 1 = 11 ejercicios. Ningún carácter se repite.
CANTIDAD_VENCIDOS = 4
CANTIDAD_ADAPTADOS = 3
CANTIDAD_REFUERZOS = 3
TOTAL_OBJETIVO = 7
MINIMO_NUEVOS = 1

# En español; serializacion.py lo traduce al idioma de la petición.
AVISO_PROGRESO = N_(
    "La respuesta quedó guardada en la sesión, pero no se pudo actualizar "
    "el progreso: el servicio de progreso no respondió."
)


class SesionEstudioService:
    """Orquesta la creación de una sesión de estudio adaptativa."""

    def __init__(self, motor, notificador, progreso):
        # Inyección de dependencias: en tests se pasan dobles;
        # en runtime las arma fabricas.py.
        self._motor = motor
        self._notificador = notificador
        self._progreso = progreso

    def crear_sesion_adaptativa(self, sesion_db, usuario_id, nivel_hsk, duracion_min=10):
        progreso = self._progreso.obtener(usuario_id)

        dificultad = self._motor.sugerir_dificultad(progreso)
        vencidos, adaptados, refuerzos, nuevos = self._elegir_caracteres(
            usuario_id, progreso, dificultad
        )

        sesion = (
            SesionEstudioBuilder()
            .para_usuario(usuario_id, progreso.get("nivel_max_desbloqueado", 1))
            .en_nivel(nivel_hsk)
            .con_dificultad(dificultad)
            .con_duracion(duracion_min)
            .agregar_vencidos(vencidos)
            .agregar_adaptados(adaptados)
            .agregar_refuerzos(refuerzos)
            .agregar_contenido_nuevo(nuevos)
            .build(SesionesRepositorio(sesion_db))
        )

        self._notificador.sesion_lista(usuario_id, sesion)
        return sesion

    def _elegir_caracteres(self, usuario_id, progreso, dificultad):
        """(vencidos, adaptados, refuerzos, nuevos), sin repetir caracteres.

        Cada lista se pide con margen (tantos como los ya elegidos) para que
        quitar repetidos no la deje más corta de lo necesario. Los adaptados
        son EjercicioAdaptado; las demás, caracteres.
        """
        vencidos = sin_repetir(
            self._progreso.repasos_vencidos(usuario_id, limite=CANTIDAD_VENCIDOS)
        )[:CANTIDAD_VENCIDOS]

        # RF-IA-03: si progreso-flask detecta patrones de error, el tutor
        # ejecuta generarEjercicioAdaptado(p) sobre ellos, del más relevante
        # al menos, hasta CANTIDAD_ADAPTADOS.
        adaptados = adaptar_a_patrones(
            self._progreso.patrones_de_error(usuario_id),
            dificultad,
            CANTIDAD_ADAPTADOS,
            excluir=vencidos,
            generar=self._motor.generar_ejercicio_adaptado,
        )

        ocupados = vencidos + [e.caracter for e in adaptados]
        refuerzos = sin_repetir(
            self._progreso.caracteres_a_reforzar(
                usuario_id, limite=CANTIDAD_REFUERZOS + len(ocupados)
            ),
            excluir=ocupados,
        )[:CANTIDAD_REFUERZOS]

        ocupados = ocupados + refuerzos
        cantidad = max(MINIMO_NUEVOS, TOTAL_OBJETIVO - len(ocupados))
        nuevos = sin_repetir(
            self._motor.seleccionar_caracteres_nuevos(progreso, cantidad=cantidad + len(ocupados)),
            excluir=ocupados,
        )[:cantidad]
        return vencidos, adaptados, refuerzos, nuevos


class ResponderEjercicioService:
    """Registra la respuesta a un ejercicio y la informa a progreso-flask.

    Si la respuesta cierra la sesión, además le pide a progreso-flask que
    aplique la curva de olvido (RF-IA-02). Si progreso no responde, queda
    una advertencia en el log y la respuesta no cambia: la sesión queda
    completada igual y no se reintenta.
    """

    def __init__(self, progreso, reloj=ahora):
        self._progreso = progreso
        self._reloj = reloj

    def responder(self, sesion_db, ejercicio_id, acerto, codigo_error=None):
        """codigo_error (RF-IA-01): tipo de error de un fallo. Se pasa a
        progreso-flask, que detecta los patrones, y desde RF-IA-02 también se
        guarda en el ejercicio para la curva de olvido. Con un acierto queda
        NULL."""
        repo = SesionesRepositorio(sesion_db)
        ejercicio = repo.obtener_ejercicio_para_responder(ejercicio_id)
        if ejercicio is None:
            raise EjercicioNoEncontradoError(N_("Ejercicio no encontrado."))
        if ejercicio.respondido:
            raise EjercicioYaRespondidoError(
                N_("El ejercicio %(id)s ya fue respondido."), id=ejercicio_id
            )

        momento = self._reloj()
        ejercicio.respondido = True
        ejercicio.fue_correcto = acerto
        ejercicio.respondido_en = momento
        # RF-IA-02: se guarda para calcular la curva de olvido al cerrar.
        ejercicio.codigo_error = None if acerto else codigo_error

        sesion = ejercicio.sesion
        sesion_cerrada = reglas.cerrar_si_completa(sesion, momento)
        pendientes = reglas.ejercicios_pendientes(sesion)
        # RF-IA-05: en cuanto termina, la sesión calcula su desempeño y
        # queda registrado en el mismo commit que la última respuesta.
        desempeno = sesion.calcular_desempeno() if sesion_cerrada else None
        if desempeno is not None:
            registrar_desempeno(sesion, desempeno)
        usuario_id, caracter = sesion.usuario_id, ejercicio.caracter

        # La respuesta se guarda antes de avisar a progreso: si progreso no
        # responde, el ejercicio igual queda respondido en la sesión.
        try:
            sesion_db.commit()
        except Exception:
            sesion_db.rollback()
            raise

        resultado = {
            "ejercicio": ejercicio,
            "sesion_completada": sesion_cerrada,
            "pendientes": pendientes,
            "proximo_repaso": None,
            "tasa_acierto": None,
        }
        if desempeno is not None:
            resultado["desempeno"] = desempeno

        progreso = self._progreso.registrar_respuesta(
            usuario_id, caracter, acerto, codigo_error=None if acerto else codigo_error
        )
        # Después de registrar la última respuesta: progreso-flask fija ahí
        # el estado inicial de un carácter con agenda anterior.
        if sesion_cerrada:
            self._aplicar_curva_olvido(sesion)

        if progreso is None:
            resultado["aviso"] = AVISO_PROGRESO
            return resultado

        # Como en v1: la fecha de repaso de ESTE carácter, en ISO con +00:00.
        racha = racha_previa(
            (progreso.get("aciertos_consecutivos") or {}).get(caracter, 0), acerto
        )
        resultado["proximo_repaso"] = calcular_proximo_repaso(racha, acerto, momento).isoformat()
        resultado["tasa_acierto"] = progreso.get("tasa_acierto")
        return resultado

    def _aplicar_curva_olvido(self, sesion):
        """Le pide a progreso-flask la curva de olvido de la sesión cerrada.

        Si falla, ProgresoRemoto ya dejó la advertencia en el log: acá no
        cambia nada de la respuesta.
        """
        cerrada_en, respuestas = resumen_para_curva(sesion)
        self._progreso.aplicar_curva_olvido(sesion.usuario_id, sesion.id, cerrada_en, respuestas)


def resumen_para_curva(sesion):
    """(cerrada_en, respuestas) de una sesión cerrada, para progreso-flask.

    cerrada_en es la fecha de la última respuesta, con zona horaria;
    respuestas, una por ejercicio respondido, en el orden de la sesión, con
    `codigo_error` solo si existe.
    """
    respondidos = [e for e in sesion.ejercicios if e.respondido]
    respuestas = []
    for e in respondidos:
        respuesta = {"caracter": e.caracter, "acerto": bool(e.fue_correcto)}
        if not e.fue_correcto and e.codigo_error:
            respuesta["codigo_error"] = e.codigo_error
        respuestas.append(respuesta)
    cerrada_en = max(e.respondido_en for e in respondidos)
    return cerrada_en.isoformat(), respuestas


def desempeno_de_sesion(sesion_db, sesion_id):
    """Desempeño de una sesión terminada (RF-IA-05)."""
    desempeno = obtener_sesion(sesion_db, sesion_id).calcular_desempeno()
    if desempeno is None:
        raise SesionNoCompletadaError(
            N_("La sesión %(id)s todavía no terminó: no tiene desempeño."), id=sesion_id
        )
    return desempeno


def historial_de_desempeno(sesion_db, usuario_id, limite):
    """Desempeño de las últimas sesiones terminadas del usuario, de la más
    reciente a la más antigua, con los totales."""
    sesiones = SesionesRepositorio(sesion_db).sesiones_completadas(usuario_id, limite)
    desempenos = [d for d in (s.calcular_desempeno() for s in sesiones) if d is not None]
    return desempenos, resumen(desempenos)


def obtener_sesion(sesion_db, sesion_id):
    sesion = SesionesRepositorio(sesion_db).obtener_sesion(sesion_id)
    if sesion is None:
        raise SesionNoEncontradaError(N_("Sesión no encontrada."))
    return sesion
