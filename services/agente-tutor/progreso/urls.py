from django.urls import path

from .views import ConsultarProgresoView

urlpatterns = [
    path(
        "progreso/<uuid:usuario_id>/",
        ConsultarProgresoView.as_view(),
        name="consultar-progreso",
    ),
]
