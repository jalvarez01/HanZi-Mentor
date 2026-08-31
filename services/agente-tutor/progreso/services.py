from .repositories import ProgresoRepository


class ProgresoService:
    def __init__(self, progreso_repo=None):
        self._progreso = progreso_repo or ProgresoRepository()

    def consultarProgreso(self, usuario_id):
        return self._progreso.obtener(usuario_id)