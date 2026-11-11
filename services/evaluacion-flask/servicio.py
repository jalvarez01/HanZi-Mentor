"""Caso de uso: decidir si la respuesta a un ejercicio es correcta.

Port de EvaluarEjercicioService (agente-tutor/tutor/services.py). No
persiste nada: registrar el resultado en la sesión y en el progreso es
trabajo de sesiones-flask (POST /api/v2/ejercicios/<id>/responder/).

Diferencias con v1:
- recibe el carácter, el tipo y la dificultad en la petición, en vez de
  leer un Ejercicio de la base de agente-tutor;
- el trazo se compara en trazos-flask con la mediana de catalogo-flask, en
  vez de pedírselo a contenido;
- si catálogo o trazos no responden, lanza DependenciaNoDisponibleError
  (503). v1 devolvía False o {"aprobado": False, "motivo": "error_servicio"},
  que el usuario no puede distinguir de un error suyo;
- el significado acierta si la respuesta se parece a la definición completa
  o a cualquiera de sus sentidos ("good" para 好). v1 solo comparaba con la
  definición completa, y un sentido correcto suelto fallaba. Las
  definiciones están en inglés: una respuesta en español no acierta;
- si la respuesta falla, el explicador (puerto ExplicadorErrores, RF-IA-04)
  agrega una explicación; si un pinyin acierta, se agrega la nota de tono, y
  si un trazo se aprueba con un tramo desviado, la nota de mejora.
  Las dos son un extra: si el explicador falla, se responde sin explicación.

Los mensajes van en español con N_ y los traduce errores.py. El 400 de
trazos-flask ya llega en el idioma del usuario, porque clientes.py le
reenvía su Accept-Language.
"""

import logging
from dataclasses import dataclass, field

from clientes import RespuestaRechazada, ServicioNoDisponible
from dominio.evaluacion import evaluar_respuesta
from dominio.excepciones import (
    CaracterNoEncontradoError,
    DependenciaNoDisponibleError,
    TrazoNoEncontradoError,
)
from dominio.explicacion import ErrorEvaluado
from dominio.notas import nota_de_mejora, nota_de_tono
from errores import ErrorDominio
from mensajes import N_

logger = logging.getLogger(__name__)

CAIDA_CATALOGO = N_("El servicio de catálogo no respondió. Probá de nuevo en unos segundos.")
CAIDA_TRAZOS = N_("El servicio de trazos no respondió. Probá de nuevo en unos segundos.")


@dataclass
class ResultadoEvaluacion:
    tipo: str
    caracter: str
    acerto: bool
    secuencia: int | None = None
    # Para trazo: el veredicto completo de trazos-flask.
    detalle_trazo: dict = field(default_factory=dict)
    # Solo si falló: por qué y qué hacer (dominio.explicacion.Explicacion).
    explicacion: object = None
    # Solo si acertó: nota de tono (pinyin) o de mejora (trazo).
    nota: object = None


class EvaluacionService:
    def __init__(self, catalogo, trazos, explicador=None):
        self._catalogo = catalogo
        self._trazos = trazos
        self._explicador = explicador

    def evaluar(self, solicitud):
        detalle = self._detalle(solicitud.caracter)

        if solicitud.tipo == "trazo":
            resultado = self._evaluar_trazo(solicitud, detalle)
            if resultado.acerto:
                resultado.nota = nota_de_mejora(detalle, resultado.secuencia, resultado.detalle_trazo)
        else:
            acerto = evaluar_respuesta(
                solicitud.tipo, solicitud.dificultad, solicitud.respuesta, detalle
            )
            resultado = ResultadoEvaluacion(solicitud.tipo, solicitud.caracter, acerto)
            if acerto and solicitud.tipo == "pinyin":
                resultado.nota = nota_de_tono(solicitud.respuesta, detalle)

        if not resultado.acerto:
            resultado.explicacion = self._explicar(solicitud, detalle, resultado)
        return resultado

    def _explicar(self, solicitud, detalle, resultado):
        if self._explicador is None:
            return None
        error = ErrorEvaluado(
            acerto=resultado.acerto,
            caracter=solicitud.caracter,
            respuesta=solicitud.respuesta,
            datos_correctos=detalle,
            dificultad=solicitud.dificultad,
            secuencia=resultado.secuencia,
            veredicto_trazo=resultado.detalle_trazo,
        )
        try:
            return self._explicador.explicar_error(solicitud.tipo, error)
        except Exception:
            # La explicación es un extra: el veredicto ya está y se responde igual.
            logger.exception("El explicador '%s' falló", getattr(self._explicador, "nombre", "?"))
            return None

    def _detalle(self, hanzi):
        try:
            return self._catalogo.obtener_detalle(hanzi)
        except RespuestaRechazada as error:
            if error.estado == 404:
                raise CaracterNoEncontradoError(
                    N_("No existe el carácter '%(hanzi)s'."), hanzi=hanzi
                ) from None
            logger.warning("El catálogo rechazó la consulta de '%s': %s", hanzi, error)
            raise DependenciaNoDisponibleError(CAIDA_CATALOGO) from None
        except ServicioNoDisponible as error:
            logger.warning("Catálogo no disponible: %s", error)
            raise DependenciaNoDisponibleError(CAIDA_CATALOGO) from None

    def _evaluar_trazo(self, solicitud, detalle):
        respuesta = solicitud.respuesta
        mediana = self._mediana(detalle, solicitud.caracter, respuesta.secuencia)

        try:
            veredicto = self._trazos.validar(
                mediana, respuesta.puntos, respuesta.ancho, respuesta.alto
            )
        except RespuestaRechazada as error:
            if error.estado == 400:
                # Los puntos del usuario no cumplen el contrato de trazos-flask.
                # Su mensaje ya viene traducido y se devuelve tal cual.
                mensaje = error.datos.get("error") or N_("Los puntos del trazo no son válidos")
                raise ErrorDominio(mensaje, "ENTRADA_INVALIDA") from None
            logger.warning("trazos-flask rechazó la validación: %s", error)
            raise DependenciaNoDisponibleError(CAIDA_TRAZOS) from None
        except ServicioNoDisponible as error:
            logger.warning("trazos-flask no disponible: %s", error)
            raise DependenciaNoDisponibleError(CAIDA_TRAZOS) from None

        return ResultadoEvaluacion(
            solicitud.tipo,
            solicitud.caracter,
            bool(veredicto.get("aprobado")),
            secuencia=respuesta.secuencia,
            detalle_trazo=veredicto,
        )

    @staticmethod
    def _mediana(detalle, hanzi, secuencia):
        for trazo in detalle.get("trazos") or []:
            if trazo.get("secuencia") == secuencia:
                mediana = trazo.get("mediana")
                if isinstance(mediana, list) and len(mediana) >= 2:
                    return mediana
                break
        # Mismo mensaje que contenido v1.
        raise TrazoNoEncontradoError(
            N_("El carácter '%(hanzi)s' no tiene un trazo con secuencia %(secuencia)s."),
            hanzi=hanzi,
            secuencia=secuencia,
        )
