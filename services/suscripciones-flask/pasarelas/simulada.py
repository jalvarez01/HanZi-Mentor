"""Pasarela simulada: no mueve dinero ni llama a ningún servicio externo.

Responde según el número de tarjeta, con los números de prueba que usan
pasarelas como Stripe:

| Número              | Resultado                              |
|---------------------|----------------------------------------|
| 4000 0000 0000 0002 | rechazada: TARJETA_RECHAZADA (402)     |
| 4000 0000 0000 9995 | rechazada: FONDOS_INSUFICIENTES (402)  |
| 4000 0000 0000 0119 | la pasarela no responde (503)          |
| cualquier otro      | aprobada (p. ej. 4242 4242 4242 4242)  |
"""

import uuid

from dominio.excepciones import PagoRechazado, PasarelaNoDisponible
from mensajes import N_
from pasarelas.base import PagoAprobado, PasarelaPago

RECHAZADA = "4000000000000002"
SIN_FONDOS = "4000000000009995"
NO_RESPONDE = "4000000000000119"


class PasarelaSimulada(PasarelaPago):
    nombre = "simulada"

    def cobrar(self, cobro):
        numero = cobro.tarjeta.numero
        if numero == RECHAZADA:
            raise PagoRechazado(N_("El banco rechazó la tarjeta."), "TARJETA_RECHAZADA")
        if numero == SIN_FONDOS:
            raise PagoRechazado(
                N_("La tarjeta no tiene fondos suficientes."), "FONDOS_INSUFICIENTES"
            )
        if numero == NO_RESPONDE:
            raise PasarelaNoDisponible(
                N_("La pasarela de pago no respondió. No se hizo ningún cobro."),
                "PASARELA_NO_DISPONIBLE",
            )
        return PagoAprobado(referencia=f"SIM-{uuid.uuid4().hex[:12].upper()}")
