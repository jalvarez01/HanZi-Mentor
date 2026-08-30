from rest_framework import serializers

from .models import Caracter, Trazo


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
