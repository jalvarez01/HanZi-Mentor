from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ProgresoUsuario
from .serializers import ProgresoUsuarioSerializer


class ConsultarProgresoView(APIView):
    """GET /api/progreso/<usuario_id>/ — estado acumulado del estudiante."""

    def get(self, request, usuario_id):
        progreso, _ = ProgresoUsuario.objects.get_or_create(usuario_id=usuario_id)
        return Response(ProgresoUsuarioSerializer(progreso).data, status=status.HTTP_200_OK)
