"""Valida la forma de la entrada antes de llegar al servicio.

Cada error se lanza como ErrorDominio con 400 y código ENTRADA_INVALIDA.
Las reglas de la tarjeta son las mismas que valida el formulario del
frontend: el cliente avisa antes de enviar y el servidor no confía en él.
"""

import re
import uuid

from errores import ErrorDominio
from mensajes import N_
from pasarelas.base import Tarjeta

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_VENCIMIENTO = re.compile(r"^(\d{2})\s*/\s*(\d{2})$")
_CVC = re.compile(r"^\d{3,4}$")

MIN_DIGITOS = 13
MAX_DIGITOS = 19
MIN_TITULAR = 2
MAX_TITULAR = 60


def _invalida(mensaje, **params):
    return ErrorDominio(mensaje, "ENTRADA_INVALIDA", params=params)


def validar_usuario_id(texto):
    if not _UUID.match(texto):
        raise _invalida(N_("El usuario_id debe ser un UUID válido"))
    return uuid.UUID(texto)


def _objeto(datos):
    if not isinstance(datos, dict):
        raise _invalida(N_("El cuerpo debe ser un objeto JSON"))
    return datos


def luhn_valido(digitos):
    """Dígito verificador de las tarjetas (algoritmo de Luhn)."""
    total = 0
    for i, c in enumerate(reversed(digitos)):
        n = int(c)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _tarjeta(pago, momento):
    if not isinstance(pago, dict):
        raise _invalida(N_("El campo 'pago' es obligatorio y debe ser un objeto"))

    numero = pago.get("numero")
    if not isinstance(numero, str):
        raise _invalida(N_("El número de tarjeta es obligatorio"))
    digitos = re.sub(r"[\s-]", "", numero)
    if (
        not digitos.isdigit()
        or not MIN_DIGITOS <= len(digitos) <= MAX_DIGITOS
        or not luhn_valido(digitos)
    ):
        raise _invalida(N_("El número de tarjeta no es válido"))

    titular = pago.get("titular")
    titular = " ".join(titular.split()) if isinstance(titular, str) else ""
    if not MIN_TITULAR <= len(titular) <= MAX_TITULAR:
        raise _invalida(
            N_("El nombre del titular debe tener entre %(minimo)s y %(maximo)s caracteres"),
            minimo=MIN_TITULAR,
            maximo=MAX_TITULAR,
        )

    vencimiento = pago.get("vencimiento")
    partes = _VENCIMIENTO.match(vencimiento.strip()) if isinstance(vencimiento, str) else None
    if not partes or not 1 <= int(partes.group(1)) <= 12:
        raise _invalida(N_("El vencimiento debe tener el formato MM/AA"))
    mes, anio = int(partes.group(1)), 2000 + int(partes.group(2))
    # Una tarjeta vale hasta el último día de su mes de vencimiento.
    if (anio, mes) < (momento.year, momento.month):
        raise _invalida(N_("La tarjeta está vencida"))

    cvc = pago.get("cvc")
    if not isinstance(cvc, str) or not _CVC.match(cvc.strip()):
        raise _invalida(N_("El código de seguridad debe tener 3 o 4 dígitos"))

    return Tarjeta(numero=digitos, titular=titular, mes=mes, anio=anio, cvc=cvc.strip())


def validar_activacion(datos, momento):
    """POST .../activar/: {"plan": "premium", "pago": {...}}."""
    datos = _objeto(datos)
    if datos.get("plan") != "premium":
        raise _invalida(
            N_("El campo 'plan' debe ser 'premium': Free es el plan por defecto y no se activa")
        )
    return _tarjeta(datos.get("pago"), momento)


def validar_renovacion(datos, momento):
    """POST .../renovar/: {"pago": {...}}."""
    return _tarjeta(_objeto(datos).get("pago"), momento)
