from django.urls import path

from .views import CrearSesionEstudioView, DetalleSesionView, ResponderEjercicioView

urlpatterns = [
    path("sesiones/", CrearSesionEstudioView.as_view(), name="crear-sesion"),
    path("sesiones/<int:sesion_id>/", DetalleSesionView.as_view(), name="detalle-sesion"),
    path(
        "ejercicios/<int:ejercicio_id>/responder/",
        ResponderEjercicioView.as_view(),
        name="responder-ejercicio",
    ),
]
