"""Puerto de pagos: lo que el servicio necesita de cualquier pasarela."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Tarjeta:
    """Datos de la tarjeta ya validados. Nunca se guardan ni se escriben en
    el log: de la tarjeta solo quedan la marca y los últimos 4 dígitos."""

    numero: str  # solo dígitos
    titular: str
    mes: int
    anio: int  # con cuatro cifras
    cvc: str

    @property
    def ultimos4(self):
        return self.numero[-4:]

    @property
    def marca(self):
        if self.numero.startswith("4"):
            return "visa"
        if self.numero[:2] in ("51", "52", "53", "54", "55") or self.numero[:1] == "2":
            return "mastercard"
        if self.numero[:2] in ("34", "37"):
            return "amex"
        return "otra"

    def __repr__(self):
        # Que un print o un traceback nunca muestren el número completo.
        return f"Tarjeta({self.marca} ****{self.ultimos4})"


@dataclass(frozen=True)
class Cobro:
    usuario_id: str
    monto: int
    moneda: str
    concepto: str  # "activacion" o "renovacion"
    tarjeta: Tarjeta


@dataclass(frozen=True)
class PagoAprobado:
    referencia: str  # identificador del cobro en la pasarela


class PasarelaPago(ABC):
    """Cobra un monto a una tarjeta.

    `cobrar` devuelve PagoAprobado, o lanza PagoRechazado si la pasarela no
    aprueba el cobro, o PasarelaNoDisponible si no responde (las dos de
    dominio.excepciones).
    """

    nombre = "base"

    @abstractmethod
    def cobrar(self, cobro: Cobro) -> PagoAprobado:
        raise NotImplementedError
