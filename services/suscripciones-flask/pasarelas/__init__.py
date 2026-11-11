"""Pasarelas de pago detrás del puerto PasarelaPago (patrón Adapter).

El servicio solo conoce la interfaz de base.py; fabrica.py elige el
adaptador según PASARELA_PAGO. Agregar una pasarela real (Wompi, Stripe...)
es escribir otro adaptador, sin tocar servicio.py.
"""
