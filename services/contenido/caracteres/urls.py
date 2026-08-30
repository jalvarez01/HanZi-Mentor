from django.urls import path

from .views import CaracteresPorNivelView, DetalleCaracterView

urlpatterns = [
    path("caracteres/", CaracteresPorNivelView.as_view(), name="caracteres-por-nivel"),
    path("caracteres/<str:hanzi>/", DetalleCaracterView.as_view(), name="detalle-caracter"),
]
