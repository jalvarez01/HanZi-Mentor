from django.urls import path
 
from .views import DetalleLeccionView, GenerarLeccionView
 
urlpatterns = [
    path("lecciones/generar/", GenerarLeccionView.as_view(), name="generar-leccion"),
    path("lecciones/<int:leccion_id>/", DetalleLeccionView.as_view(), name="detalle-leccion"),
]