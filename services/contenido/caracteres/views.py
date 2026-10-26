from django.utils.translation import gettext
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .domain.exceptions import CaracterNoEncontradoError, TrazoNoEncontradoError
from .models import Caracter
from .serializers import (
    CaracterListaSerializer,
    CaracterSerializer,
    ResultadoComparacionSerializer,
    ValidacionTrazoSerializer,
)
from .services import ValidacionTrazoService


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
            return Response({"error": gettext("Carácter no encontrado.")}, status=status.HTTP_404_NOT_FOUND)

        return Response(CaracterSerializer(caracter).data, status=status.HTTP_200_OK)


class ValidarTrazoView(APIView):
    """POST /api/caracteres/<hanzi>/trazos/<secuencia>/validar/"""

    def __init__(self, service=None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or ValidacionTrazoService()

    def post(self, request, hanzi, secuencia):
        entrada = ValidacionTrazoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        try:
            resultado = self.service.validar(hanzi, secuencia, **entrada.validated_data)
        except (CaracterNoEncontradoError, TrazoNoEncontradoError) as error:
            return Response({"error": str(error)}, status=status.HTTP_404_NOT_FOUND)

        datos = ResultadoComparacionSerializer(resultado).data
        # El comparador es dominio puro y no importa Django: deja el detalle
        # en español (marcado para makemessages) y se traduce acá.
        datos["detalle"] = gettext(datos["detalle"]) if datos["detalle"] else datos["detalle"]
        return Response(datos, status=status.HTTP_200_OK)
