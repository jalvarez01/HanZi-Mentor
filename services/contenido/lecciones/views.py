from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Leccion
from .serializers import GenerarLeccionSerializer, LeccionSerializer


class GenerarLeccionView(APIView):
    """POST /api/lecciones/generar/ — crea una Leccion y ejecuta generarContenido()."""

    def post(self, request):
        entrada = GenerarLeccionSerializer(data=request.data)
        if not entrada.is_valid():
            return Response(entrada.errors, status=status.HTTP_400_BAD_REQUEST)

        datos = entrada.validated_data
        leccion = Leccion.objects.create(
            usuario_id=datos["usuario_id"], nivel_hsk=datos["nivel_hsk"]
        )
        leccion.generarContenido(cantidad=datos["cantidad"])

        return Response(LeccionSerializer(leccion).data, status=status.HTTP_201_CREATED)


class DetalleLeccionView(APIView):
    """GET /api/lecciones/<id>/ — detalle de la Leccion con sus Ejercicios."""

    def get(self, request, leccion_id):
        leccion = Leccion.objects.prefetch_related("ejercicios__caracter").filter(
            id=leccion_id
        ).first()

        if leccion is None:
            return Response(
                {"error": "Lección no encontrada."}, status=status.HTTP_404_NOT_FOUND
            )

        return Response(LeccionSerializer(leccion).data, status=status.HTTP_200_OK)