"""
Patrón Factory: arma los clientes de los servicios de los que depende,
según la configuración (CATALOGO_URL, TRAZOS_URL, HTTP_TIMEOUT,
HTTP_REINTENTOS).
"""

from dataclasses import dataclass

from clientes import CatalogoRemoto, ClienteHttp, TrazosRemoto


@dataclass
class Dependencias:
    catalogo: CatalogoRemoto
    trazos: TrazosRemoto


def _cliente(config, clave):
    return ClienteHttp(
        config[clave],
        timeout=config["HTTP_TIMEOUT"],
        reintentos=config["HTTP_REINTENTOS"],
    )


def crear_dependencias(config):
    return Dependencias(
        catalogo=CatalogoRemoto(_cliente(config, "CATALOGO_URL")),
        trazos=TrazosRemoto(_cliente(config, "TRAZOS_URL")),
    )
