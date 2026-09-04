"""Acceso a datos de progreso. Aísla al Service de cómo se guarda la información."""

from .models import ProgresoUsuario


class ProgresoRepository:
    def obtener(self, usuario_id) -> dict:
        progreso = ProgresoUsuario.objects.filter(usuario_id=usuario_id).first()

        if progreso is None:
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

        caracteres_dominados = progreso.caracteres_dominados or []
        errores_frecuentes = progreso.errores_frecuentes or {}
        ordenados = sorted(
            errores_frecuentes.items(), key=lambda par: par[1], reverse=True
        )

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
                for caracter, fallos in ordenados[:5]
            ],
        }

    def caracteres_a_reforzar(self, usuario_id, limite=3) -> list:
        progreso = ProgresoUsuario.objects.filter(usuario_id=usuario_id).first()
        if progreso is None:
            return []

        errores = progreso.errores_frecuentes or {}
        ordenados = sorted(errores.items(), key=lambda par: par[1], reverse=True)
        return [caracter for caracter, _ in ordenados[:limite]]

    # ---------- escritura ----------

    def obtener_o_crear_entidad(self, usuario_id) -> ProgresoUsuario:
        """Devuelve la entidad real (no el dict) para poder mutarla y guardarla."""
        progreso, _ = ProgresoUsuario.objects.get_or_create(usuario_id=usuario_id)
        return progreso

    def guardar(self, progreso: ProgresoUsuario) -> None:
        progreso.save()