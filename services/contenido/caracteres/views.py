from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Caracter
from .serializers import CaracterListaSerializer, CaracterSerializer


class CaracteresPorNivelView(APIView):
    """GET /api/caracteres/?nivel=2&excluir=学,校&limite=4"""

    def get(self, request):
        nivel = request.query_params.get("nivel")
        limite = int(request.query_params.get("limite", 20))
        excluir = [c for c in request.query_params.get("excluir", "").split(",") if c]

        consulta = Caracter.objects.all()
        if nivel:
            consulta = consulta.filter(nivel_hsk=nivel)
        if excluir:
            consulta = consulta.exclude(hanzi__in=excluir)

        datos = CaracterListaSerializer(consulta[:limite], many=True).data
        return Response({"caracteres": datos}, status=status.HTTP_200_OK)


class DetalleCaracterView(APIView):
    """GET /api/caracteres/<hanzi>/ — incluye los trazos en orden."""

    def get(self, request, hanzi):
        caracter = Caracter.objects.filter(hanzi=hanzi).prefetch_related("trazos").first()

        if caracter is None:
            return Response({"error": "Carácter no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        return Response(CaracterSerializer(caracter).data, status=status.HTTP_200_OK)
