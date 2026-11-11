"""Errores con que termina una tarea de reporte.

Celery guarda la excepción en Redis como JSON con su tipo, su módulo y sus
`args`, y al leerla la vuelve a crear con `cls(*args)`. Por eso `args` es
exactamente (codigo, mensaje): llega igual a la app Flask, que traduce el
mensaje y responde el código. El traceback queda en Redis y nunca se
devuelve.

El mensaje va en español, marcado con N_; se traduce al responder.
"""

from mensajes import N_


class ErrorReporte(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(codigo, mensaje)
        self.codigo = codigo
        self.mensaje = mensaje

    def __str__(self):
        return f"{self.codigo}: {self.mensaje}"


class DependenciaNoDisponible(ErrorReporte):
    """progreso-flask no respondió. Es el único error que Celery reintenta."""

    def __init__(
        self,
        codigo="DEPENDENCIA_NO_DISPONIBLE",
        mensaje=N_("El servicio de progreso no respondió. Probá de nuevo en unos segundos."),
    ):
        super().__init__(codigo, mensaje)


# Cualquier otra falla (por ejemplo, el límite de 30 s) se responde así.
CODIGO_GENERICO = "ERROR_INTERNO"
MENSAJE_GENERICO = N_("No se pudo generar el reporte.")
