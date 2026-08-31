from rest_framework import serializers

from .models import Caracter, Trazo


class PuntoField(serializers.Field):
    """Un punto como [x, y] o {"x": x, "y": y}. El comparador acepta ambas formas."""

    def to_internal_value(self, data):
        if isinstance(data, dict):
            if "x" not in data or "y" not in data:
                raise serializers.ValidationError("El punto debe tener 'x' e 'y'.")
            x, y = data["x"], data["y"]
        elif isinstance(data, (list, tuple)):
            if len(data) != 2:
                raise serializers.ValidationError("El punto debe ser [x, y].")
            x, y = data
        else:
            raise serializers.ValidationError("El punto debe ser [x, y] o {'x': x, 'y': y}.")

        try:
            return [float(x), float(y)]
        except (TypeError, ValueError):
            raise serializers.ValidationError("Las coordenadas del punto deben ser numéricas.")

    def to_representation(self, value):
        return value


class ValidacionTrazoSerializer(serializers.Serializer):
    """Valida la forma del request. No contiene reglas de negocio."""

    puntos = serializers.ListField(
        child=PuntoField(), min_length=2,
        error_messages={"min_length": "Se necesitan al menos 2 puntos para un trazo."},
    )
    ancho = serializers.IntegerField(min_value=1)
    alto = serializers.IntegerField(min_value=1)


class ResultadoComparacionSerializer(serializers.Serializer):
    """Salida: el veredicto de la comparación."""

    aprobado = serializers.BooleanField(read_only=True)
    puntaje = serializers.IntegerField(read_only=True)
    motivo = serializers.CharField(read_only=True)
    invertido = serializers.BooleanField(read_only=True)
    detalle = serializers.CharField(read_only=True)
    distancia_media = serializers.FloatField(read_only=True)
    razon_longitud = serializers.FloatField(read_only=True)
    puntos_lejanos = serializers.ListField(read_only=True)


class TrazoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trazo
        fields = ["secuencia", "path_svg", "mediana"]


class CaracterSerializer(serializers.ModelSerializer):
    trazos = TrazoSerializer(many=True, read_only=True)

    class Meta:
        model = Caracter
        fields = [
            "hanzi", "pinyin", "definicion", "radical",
            "descomposicion", "nivel_hsk", "trazos",
        ]


class CaracterListaSerializer(serializers.ModelSerializer):
    """Versión liviana: sin trazos, para listados."""

    class Meta:
        model = Caracter
        fields = ["hanzi", "pinyin", "definicion", "nivel_hsk"]
