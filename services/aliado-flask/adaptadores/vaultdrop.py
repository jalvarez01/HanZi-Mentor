"""Adaptador real: el catálogo público de VaultDrop.

Usa GET /api/v2/catalogo/ de su microservicio Flask (detrás de su Nginx),
que es público: no pide login ni créditos. Responde la lista de cajas
activas, cada una con sus ítems y la probabilidad de cada ítem.

Traduce esa respuesta al modelo del dominio (`Caja`, `Item`) y convierte
cualquier falla de red o de formato en `AliadoNoDisponible`. Las imágenes
llegan con ruta relativa (/static/...): se completan con la URL del aliado.
"""

import http.client
import json
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

from dominio.caja import Caja, Item
from dominio.puertos import AliadoNoDisponible, ProveedorCajas

_AGENTE = "HanZi-Mentor/1.0 (proyecto académico, Universidad EAFIT)"
RUTA_CATALOGO = "/api/v2/catalogo/"


def obtener_json(url, timeout):
    """GET que devuelve el JSON de la respuesta. Lanza AliadoNoDisponible."""
    peticion = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": _AGENTE}
    )
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            return json.load(respuesta)
    except (OSError, http.client.HTTPException, ValueError) as error:
        # OSError cubre errores HTTP 4xx/5xx, timeouts y conexiones cortadas;
        # HTTPException, respuestas incompletas; ValueError, JSON inválido.
        raise AliadoNoDisponible(f"VaultDrop no respondió: {error}") from error


class AdaptadorVaultDrop(ProveedorCajas):
    nombre = "vaultdrop"

    def __init__(self, url_base, timeout, obtener=obtener_json):
        if not url_base:
            raise ValueError("ALIADO_URL es obligatoria con ALIADO_PROVEEDOR=vaultdrop")
        self._url_base = url_base.rstrip("/")
        self._timeout = timeout
        # Inyectable para probar el adaptador sin salir a la red.
        self._obtener = obtener

    def obtener_cajas(self):
        datos = self._obtener(self._url_base + RUTA_CATALOGO, self._timeout)
        try:
            return [self._a_caja(caja) for caja in datos]
        except (KeyError, TypeError, AttributeError, InvalidOperation) as error:
            raise AliadoNoDisponible(f"Respuesta de VaultDrop inesperada: {error!r}") from error

    def _a_caja(self, caja):
        return Caja(
            id=int(caja["id"]),
            nombre=caja["nombre"],
            precio=str(caja.get("precio", "")),
            imagen_url=self._absoluta(caja.get("imagen_url")),
            items=tuple(self._a_item(entrada) for entrada in caja.get("items", [])),
        )

    def _a_item(self, entrada):
        item = entrada["item"]
        return Item(
            nombre=item["nombre"],
            rareza=item.get("rareza", ""),
            valor_estimado=str(item.get("valor_estimado", "")),
            imagen_url=self._absoluta(item.get("imagen_url")),
            probabilidad=Decimal(str(entrada["probabilidad"])),
        )

    def _absoluta(self, ruta):
        if not ruta:
            return ""
        return urllib.parse.urljoin(self._url_base + "/", ruta)
