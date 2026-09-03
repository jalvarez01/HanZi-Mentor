from rest_framework import serializers

from caracteres.serializers import CaracterListaSerializer

from .models import Ejercicio, Leccion


class EjercicioSerializer(serializers.ModelSerializer):
    caracter = CaracterListaSerializer(read_only=True)

    class Meta:
        model = Ejercicio
        fields = ["id", "tipo", "caracter", "completado"]


class LeccionSerializer(serializers.ModelSerializer):
    """Salida: detalle de una Leccion con sus Ejercicios ya generados."""

    ejercicios = EjercicioSerializer(many=True, read_only=True)

    class Meta:
        model = Leccion
        fields = ["id", "usuario_id", "nivel_hsk", "creada_en", "ejercicios"]


class GenerarLeccionSerializer(serializers.Serializer):
    """Entrada: datos para POST /api/lecciones/generar/"""

    usuario_id = serializers.UUIDField()
    nivel_hsk = serializers.IntegerField(min_value=1, max_value=6)
    cantidad = serializers.IntegerField(min_value=1, max_value=50, default=10)