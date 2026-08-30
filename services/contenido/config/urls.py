"""Rutas del servicio contenido."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("caracteres.urls")),
]
