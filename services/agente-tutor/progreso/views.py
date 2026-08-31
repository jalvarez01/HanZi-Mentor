from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import ProgresoService


class ConsultarProgresoView(APIView):
    """GET /api/progreso/<usuario_id>/ — estado acumulado del estudiante."""

    def __init__(self, service=None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or ProgresoService()

    def get(self, request, usuario_id):
        resultado = self.service.consultarProgreso(usuario_id)
        return Response(resultado, status=status.HTTP_200_OK)
