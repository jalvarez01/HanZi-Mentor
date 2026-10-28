"""
Patrón Factory: decide qué implementación concreta se usa, según la
configuración. Port de agente-tutor/tutor/infra/factories.py.

    TUTOR_ENGINE = MOCK      (REAL, con LangGraph, sigue en agente-tutor)
    NOTIFICADOR  = consola | cola   (console, el valor anterior, es alias de consola)
    REDIS_URL, REDIS_TIMEOUT        (solo con NOTIFICADOR=cola)
    CATALOGO_URL, PROGRESO_URL, HTTP_TIMEOUT, HTTP_REINTENTOS

Una opción que no existe falla al arrancar, no en la primera petición.
"""

from dataclasses import dataclass

from clientes import CatalogoRemoto, ClienteHttp, ProgresoRemoto
from motores import MotorTutor, MotorTutorMock
from notificadores import Notificador, NotificadorCola, NotificadorConsola, crear_publicador


@dataclass
class Dependencias:
    motor: MotorTutor
    notificador: Notificador
    progreso: ProgresoRemoto


def _cliente(config, clave):
    return ClienteHttp(
        config[clave],
        timeout=config["HTTP_TIMEOUT"],
        reintentos=config["HTTP_REINTENTOS"],
    )


def crear_motor(config, catalogo):
    modo = config["TUTOR_ENGINE"]
    if modo == "MOCK":
        return MotorTutorMock(catalogo=catalogo)
    raise ValueError(
        f"TUTOR_ENGINE='{modo}' no está disponible en sesiones-flask: solo MOCK. "
        "El motor LangGraph sigue en agente-tutor."
    )


def crear_notificador(config):
    modo = config["NOTIFICADOR"].strip().lower()
    if modo in ("consola", "console"):
        return NotificadorConsola()
    if modo == "cola":
        # Perezoso: no conecta con Redis hasta la primera sesión.
        return NotificadorCola(crear_publicador(config["REDIS_URL"], config["REDIS_TIMEOUT"]))
    raise ValueError(
        f"NOTIFICADOR='{config['NOTIFICADOR']}' no existe en sesiones-flask: consola o cola."
    )


def crear_dependencias(config):
    catalogo = CatalogoRemoto(_cliente(config, "CATALOGO_URL"))
    return Dependencias(
        motor=crear_motor(config, catalogo),
        notificador=crear_notificador(config),
        progreso=ProgresoRemoto(_cliente(config, "PROGRESO_URL")),
    )
