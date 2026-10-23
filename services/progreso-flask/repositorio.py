"""Acceso a datos de progreso. Aísla al servicio de cómo se guarda la información.

Port de services/agente-tutor/progreso/repositories.py.
"""

from sqlalchemy import select

from dominio.progreso import peores_caracteres
from modelos import ProgresoUsuario

# Cuántos caracteres débiles se muestran en el resumen.
TOTAL_DEBILES = 5


def progreso_inicial(usuario_id):
    """Lo que ve un usuario que todavía no respondió nada (no se guarda)."""
    return {
        "usuario_id": str(usuario_id),
        "nivel_hsk": 1,
        "nivel_max_desbloqueado": 1,
        "tasa_acierto": 0.5,
        "caracteres_dominados": [],
        "errores_frecuentes": {},
        "aciertos_consecutivos": {},
        "proximo_repaso": None,
        "actualizado_en": None,
        "total_dominados": 0,
        "total_por_reforzar": 0,
        "caracteres_debiles": [],
    }


class ProgresoRepositorio:
    def __init__(self, sesion):
        self._sesion = sesion

    def _buscar(self, usuario_id, bloquear=False):
        consulta = select(ProgresoUsuario).where(ProgresoUsuario.usuario_id == usuario_id)
        if bloquear:
            # En PostgreSQL evita que dos respuestas del mismo usuario se pisen.
            consulta = consulta.with_for_update()
        return self._sesion.scalars(consulta).first()

    def obtener(self, usuario_id) -> dict:
        progreso = self._buscar(usuario_id)
        if progreso is None:
            return progreso_inicial(usuario_id)

        caracteres_dominados = progreso.caracteres_dominados or []
        errores_frecuentes = progreso.errores_frecuentes or {}

        return {
            "usuario_id": str(progreso.usuario_id),
            "nivel_hsk": progreso.nivel_hsk,
            "nivel_max_desbloqueado": progreso.nivel_max_desbloqueado,
            "tasa_acierto": progreso.tasa_acierto,
            "caracteres_dominados": caracteres_dominados,
            "errores_frecuentes": errores_frecuentes,
            "aciertos_consecutivos": progreso.aciertos_consecutivos or {},
            "proximo_repaso": progreso.proximo_repaso,
            "actualizado_en": progreso.actualizado_en,
            "total_dominados": len(caracteres_dominados),
            "total_por_reforzar": len(errores_frecuentes),
            "caracteres_debiles": [
                {"caracter": caracter, "fallos": fallos}
                for caracter, fallos in peores_caracteres(errores_frecuentes, TOTAL_DEBILES)
            ],
        }

    def caracteres_a_reforzar(self, usuario_id, limite=3) -> list:
        progreso = self._buscar(usuario_id)
        if progreso is None:
            return []
        return [c for c, _ in peores_caracteres(progreso.errores_frecuentes, limite)]

    # ---------- escritura ----------

    def obtener_o_crear_entidad(self, usuario_id) -> ProgresoUsuario:
        """Devuelve la entidad real (no el dict) para poder mutarla y guardarla."""
        progreso = self._buscar(usuario_id, bloquear=True)
        if progreso is None:
            progreso = ProgresoUsuario(usuario_id=usuario_id)
            self._sesion.add(progreso)
        return progreso

    def guardar(self, progreso: ProgresoUsuario) -> None:
        self._sesion.add(progreso)
        self._sesion.flush()
