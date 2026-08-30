from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .domain.exceptions import DominioError
from .models import Ejercicio, SesionEstudio
from .serializers import (
    CrearSesionSerializer,
    ResponderEjercicioSerializer,
    ResultadoRespuestaSerializer,
    SesionEstudioSerializer,
)
from .services import ResponderEjercicioService, SesionEstudioService


class CrearSesionEstudioView(APIView):
    """POST /api/sesiones/ — captura el request y delega. Nada más."""

    def __init__(self, service=None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or SesionEstudioService()

    def post(self, request):
        entrada = CrearSesionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        try:
            sesion = self.service.crear_sesion_adaptativa(**entrada.validated_data)
        except DominioError as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        salida = SesionEstudioSerializer(sesion)
        return Response(salida.data, status=status.HTTP_201_CREATED)


class ResponderEjercicioView(APIView):
    """POST /api/ejercicios/<id>/responder/ — captura el request y delega."""

    def __init__(self, service=None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or ResponderEjercicioService()

    def post(self, request, ejercicio_id):
        entrada = ResponderEjercicioSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        try:
            resultado = self.service.responder(ejercicio_id, **entrada.validated_data)
        except Ejercicio.DoesNotExist:
            return Response({"error": "Ejercicio no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except DominioError as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ResultadoRespuestaSerializer(resultado).data, status=status.HTTP_200_OK)


class DetalleSesionView(APIView):
    """GET /api/sesiones/<id>/ — permite retomar una sesión en curso."""

    def get(self, request, sesion_id):
        sesion = (
            SesionEstudio.objects
            .filter(pk=sesion_id)
            .prefetch_related("ejercicios")
            .first()
        )

        if sesion is None:
            return Response({"error": "Sesión no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        return Response(SesionEstudioSerializer(sesion).data, status=status.HTTP_200_OK)
