from rest_framework import serializers

from .models import ProgresoUsuario


class ProgresoUsuarioSerializer(serializers.ModelSerializer):
    total_dominados = serializers.SerializerMethodField()
    total_por_reforzar = serializers.SerializerMethodField()
    caracteres_debiles = serializers.SerializerMethodField()

    class Meta:
        model = ProgresoUsuario
        fields = [
            "usuario_id",
            "nivel_hsk",
            "nivel_max_desbloqueado",
            "tasa_acierto",
            "caracteres_dominados",
            "errores_frecuentes",
            "aciertos_consecutivos",
            "proximo_repaso",
            "actualizado_en",
            "total_dominados",
            "total_por_reforzar",
            "caracteres_debiles",
        ]

    def get_total_dominados(self, obj):
        return len(obj.caracteres_dominados or [])

    def get_total_por_reforzar(self, obj):
        return len(obj.errores_frecuentes or {})

    def get_caracteres_debiles(self, obj):
        """Los cinco que más se fallan, de peor a mejor."""
        errores = obj.errores_frecuentes or {}
        ordenados = sorted(errores.items(), key=lambda par: par[1], reverse=True)
        return [{"caracter": c, "fallos": n} for c, n in ordenados[:5]]
