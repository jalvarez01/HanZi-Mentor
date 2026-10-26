"""
Patrón Factory: arma los clientes de los servicios de los que depende,
según la configuración (CATALOGO_URL, TRAZOS_URL, HTTP_TIMEOUT,
HTTP_REINTENTOS).
"""

from dataclasses import dataclass

from flask import has_request_context, request

from clientes import CatalogoRemoto, ClienteHttp, TrazosRemoto


@dataclass
class Dependencias:
    catalogo: CatalogoRemoto
    trazos: TrazosRemoto


def idioma_del_usuario():
    """El Accept-Language de la petición que se está atendiendo, para
    reenviarlo a catálogo y trazos: así sus errores vuelven en ese idioma."""
    if has_request_context() and request.headers.get("Accept-Language"):
        return {"Accept-Language": request.headers["Accept-Language"]}
    return {}


def _cliente(config, clave):
    return ClienteHttp(
        config[clave],
        timeout=config["HTTP_TIMEOUT"],
        reintentos=config["HTTP_REINTENTOS"],
        cabeceras=idioma_del_usuario,
    )


def crear_dependencias(config):
    return Dependencias(
        catalogo=CatalogoRemoto(_cliente(config, "CATALOGO_URL")),
        trazos=TrazosRemoto(_cliente(config, "TRAZOS_URL")),
    )
