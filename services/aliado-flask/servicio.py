"""Casos de uso: listar las cajas del aliado y abrir una.

`CatalogoAliado` guarda el último catálogo que respondió:
- durante FRESCO_SEG segundos lo reutiliza sin volver a llamar al aliado;
- después lo vuelve a pedir, y si el aliado no responde usa el guardado
  (`respaldo: true`), así la sección no se cae aunque VaultDrop esté apagado;
- si el aliado nunca respondió, no hay nada que mostrar: 503.

Vive en memoria. Por eso el Dockerfile usa un solo proceso de gunicorn con
varios hilos: todas las peticiones comparten el mismo respaldo. Al reiniciar
el contenedor se pierde y se vuelve a llenar con la primera respuesta.
"""

import random
import threading
import time

from dominio.caja import CajaSinItems, sortear
from dominio.puertos import AliadoNoDisponible
from errores import ErrorDominio
from mensajes import N_

FRESCO_SEG = 60


class CatalogoAliado:
    def __init__(self, proveedor, reloj=time.monotonic, fresco_seg=FRESCO_SEG):
        self.proveedor = proveedor
        self._reloj = reloj
        self._fresco_seg = fresco_seg
        self._cajas = None
        self._pedido_en = None
        self._candado = threading.Lock()

    def cajas(self):
        """(cajas, respaldo). Lanza ErrorDominio 503 si no hay ninguna guardada."""
        with self._candado:
            ahora = self._reloj()
            if self._cajas is not None and ahora - self._pedido_en < self._fresco_seg:
                return self._cajas, False
            try:
                self._cajas = self.proveedor.obtener_cajas()
                self._pedido_en = ahora
                return self._cajas, False
            except AliadoNoDisponible:
                if self._cajas is None:
                    raise ErrorDominio(
                        N_("VaultDrop no respondió. Intentá de nuevo en un momento."),
                        "ALIADO_NO_DISPONIBLE",
                        estado=503,
                    ) from None
                return self._cajas, True


def abrir_caja(catalogo, caja_id, rng=random):
    """(caja, item, respaldo). 404 si la caja no existe."""
    cajas, respaldo = catalogo.cajas()
    caja = next((c for c in cajas if c.id == caja_id), None)
    if caja is None:
        raise ErrorDominio(N_("Caja no encontrada."), "NO_ENCONTRADO", estado=404)
    try:
        return caja, sortear(caja, rng), respaldo
    except CajaSinItems:
        raise ErrorDominio(
            N_("La caja no tiene ítems para sortear."), "CAJA_SIN_ITEMS", estado=409
        ) from None
