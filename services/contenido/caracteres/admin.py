from django.contrib import admin

from .models import Caracter, Trazo


class TrazoInline(admin.TabularInline):
    model = Trazo
    extra = 0
    fields = ("secuencia", "path_svg")


@admin.register(Caracter)
class CaracterAdmin(admin.ModelAdmin):
    list_display = ("hanzi", "pinyin", "nivel_hsk", "radical", "total_trazos")
    list_filter = ("nivel_hsk",)
    search_fields = ("hanzi", "pinyin", "definicion")
    inlines = [TrazoInline]

    @admin.display(description="Trazos")
    def total_trazos(self, obj):
        """Solo para la lista del admin: no es lógica de negocio del modelo."""
        return obj.trazos.count()
