from django.contrib import admin

from .models import Ejercicio, Leccion


class EjercicioInline(admin.TabularInline):
    model = Ejercicio
    extra = 0
    fields = ("caracter", "tipo", "completado")


@admin.register(Leccion)
class LeccionAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario_id", "nivel_hsk", "creada_en")
    list_filter = ("nivel_hsk",)
    inlines = [EjercicioInline]


@admin.register(Ejercicio)
class EjercicioAdmin(admin.ModelAdmin):
    list_display = ("id", "leccion", "caracter", "tipo", "completado")
    list_filter = ("tipo", "completado")