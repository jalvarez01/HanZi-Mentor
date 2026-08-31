from django.urls import path

from .views import CaracteresPorNivelView, DetalleCaracterView, ValidarTrazoView

urlpatterns = [
    path("caracteres/", CaracteresPorNivelView.as_view(), name="caracteres-por-nivel"),
    path("caracteres/<str:hanzi>/", DetalleCaracterView.as_view(), name="detalle-caracter"),
    path(
        "caracteres/<str:hanzi>/trazos/<int:secuencia>/validar/",
        ValidarTrazoView.as_view(),
        name="validar-trazo",
    ),
]
