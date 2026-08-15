from django.urls import path

from .views import CrearSesionEstudioView

urlpatterns = [
    path("sesiones/", CrearSesionEstudioView.as_view(), name="crear-sesion"),
]
