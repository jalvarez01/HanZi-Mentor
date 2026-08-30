from rest_framework import serializers

from .models import Ejercicio, SesionEstudio


class CrearSesionSerializer(serializers.Serializer):
    """Valida la forma del request. No contiene reglas de negocio."""

    usuario_id = serializers.UUIDField()
    nivel_hsk = serializers.IntegerField(min_value=1, max_value=6)
    duracion_min = serializers.IntegerField(min_value=5, max_value=60, default=10)


class EjercicioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ejercicio
        fields = ["id", "caracter", "tipo", "dificultad", "es_refuerzo"]


class SesionEstudioSerializer(serializers.ModelSerializer):
    ejercicios = EjercicioSerializer(many=True, read_only=True)

    class Meta:
        model = SesionEstudio
        fields = [
            "id",
            "usuario_id",
            "nivel_hsk",
            "dificultad",
            "estado",
            "duracion_estimada_min",
            "creada_en",
            "ejercicios",
        ]


class ResponderEjercicioSerializer(serializers.Serializer):
    """Valida la forma de la respuesta a un ejercicio."""

    acerto = serializers.BooleanField()


class ResultadoRespuestaSerializer(serializers.Serializer):
    """Salida tras responder: qué pasó con el ejercicio y qué sigue."""

    ejercicio = EjercicioSerializer(read_only=True)
    sesion_completada = serializers.BooleanField(read_only=True)
    pendientes = serializers.IntegerField(read_only=True)
    proximo_repaso = serializers.CharField(read_only=True, allow_null=True)
    tasa_acierto = serializers.FloatField(read_only=True)
