from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .domain.exceptions import DominioError
from .serializers import CrearSesionSerializer, SesionEstudioSerializer
from .services import SesionEstudioService


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
