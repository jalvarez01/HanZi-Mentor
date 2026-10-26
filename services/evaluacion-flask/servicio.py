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
  que el usuario no puede distinguir de un error suyo.
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
from errores import ErrorDominio

logger = logging.getLogger(__name__)


@dataclass
class ResultadoEvaluacion:
    tipo: str
    caracter: str
    acerto: bool
    secuencia: int | None = None
    # Para trazo: el veredicto completo de trazos-flask.
    detalle_trazo: dict = field(default_factory=dict)


class EvaluacionService:
    def __init__(self, catalogo, trazos):
        self._catalogo = catalogo
        self._trazos = trazos

    def evaluar(self, solicitud):
        detalle = self._detalle(solicitud.caracter)

        if solicitud.tipo == "trazo":
            return self._evaluar_trazo(solicitud, detalle)

        acerto = evaluar_respuesta(
            solicitud.tipo, solicitud.dificultad, solicitud.respuesta, detalle
        )
        return ResultadoEvaluacion(solicitud.tipo, solicitud.caracter, acerto)

    def _detalle(self, hanzi):
        try:
            return self._catalogo.obtener_detalle(hanzi)
        except RespuestaRechazada as error:
            if error.estado == 404:
                raise CaracterNoEncontradoError(f"No existe el carácter '{hanzi}'.") from None
            logger.warning("El catálogo rechazó la consulta de '%s': %s", hanzi, error)
            raise self._caida("catálogo") from None
        except ServicioNoDisponible as error:
            logger.warning("Catálogo no disponible: %s", error)
            raise self._caida("catálogo") from None

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
                mensaje = error.datos.get("error", "Los puntos del trazo no son válidos")
                raise ErrorDominio(mensaje, "ENTRADA_INVALIDA") from None
            logger.warning("trazos-flask rechazó la validación: %s", error)
            raise self._caida("trazos") from None
        except ServicioNoDisponible as error:
            logger.warning("trazos-flask no disponible: %s", error)
            raise self._caida("trazos") from None

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
            f"El carácter '{hanzi}' no tiene un trazo con secuencia {secuencia}."
        )

    @staticmethod
    def _caida(nombre):
        return DependenciaNoDisponibleError(
            f"El servicio de {nombre} no respondió. Probá de nuevo en unos segundos."
        )
