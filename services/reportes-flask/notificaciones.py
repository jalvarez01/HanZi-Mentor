"""Notificaciones de "sesión lista" por usuario.

Cada usuario tiene una lista Redis `notificaciones:<usuario_id>` con las
últimas 20, de la más nueva a la más vieja. La lista caduca a los 7 días
sin notificaciones nuevas: al tener caducidad, Redis también la puede
expulsar si se queda sin memoria (volatile-lru), nunca la cola de tareas.
"""

import json

MAXIMO = 20
CADUCIDAD_SEGUNDOS = 7 * 24 * 3600


def clave(usuario_id):
    return f"notificaciones:{usuario_id}"


class NotificacionesRedis:
    def __init__(self, cliente):
        self._cliente = cliente

    def agregar(self, usuario_id, notificacion):
        k = clave(usuario_id)
        # En una transacción: nunca queda una lista sin recortar o sin caducidad.
        with self._cliente.pipeline(transaction=True) as pipe:
            pipe.lpush(k, json.dumps(notificacion, ensure_ascii=False))
            pipe.ltrim(k, 0, MAXIMO - 1)
            pipe.expire(k, CADUCIDAD_SEGUNDOS)
            pipe.execute()

    def listar(self, usuario_id):
        return [json.loads(item) for item in self._cliente.lrange(clave(usuario_id), 0, MAXIMO - 1)]


class NotificacionesEnMemoria:
    """Doble para las pruebas, con las mismas reglas que la versión Redis."""

    def __init__(self):
        self.listas = {}
        self.caducidad = {}

    def agregar(self, usuario_id, notificacion):
        k = clave(usuario_id)
        self.listas[k] = [notificacion, *self.listas.get(k, [])][:MAXIMO]
        self.caducidad[k] = CADUCIDAD_SEGUNDOS

    def listar(self, usuario_id):
        return list(self.listas.get(clave(usuario_id), []))
