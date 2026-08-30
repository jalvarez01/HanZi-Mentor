"""
Asigna el nivel HSK a caracteres que ya están en la base.

Pensado para el flujo de clasificar de a poco: primero se importan todos los
caracteres con `cargar_hanzi --todos`, y a medida que se van completando las
listas en `caracteres/hsk.py`, este comando actualiza los niveles sin volver
a leer los archivos de Make Me a Hanzi.

Uso:
    python manage.py clasificar_hsk
    python manage.py clasificar_hsk --revisar     (no guarda, solo informa)
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from caracteres.hsk import CARACTERES_POR_NIVEL
from caracteres.models import Caracter


class Command(BaseCommand):
    help = "Asigna nivel HSK a los caracteres ya importados, según caracteres/hsk.py"

    def add_arguments(self, parser):
        parser.add_argument(
            "--revisar",
            action="store_true",
            help="Muestra qué cambiaría, sin guardar nada.",
        )

    def handle(self, *args, **opciones):
        solo_revisar = opciones["revisar"]

        nivel_de = {
            hanzi: nivel
            for nivel, caracteres in CARACTERES_POR_NIVEL.items()
            for hanzi in caracteres
        }

        self.stdout.write(f"Listas actuales: {len(nivel_de)} caracteres clasificados.")

        en_base = {c.hanzi: c for c in Caracter.objects.all()}
        self.stdout.write(f"En la base: {len(en_base)} caracteres.")

        por_actualizar = []
        faltantes = []

        for hanzi, nivel in nivel_de.items():
            caracter = en_base.get(hanzi)

            if caracter is None:
                faltantes.append(hanzi)
                continue

            if caracter.nivel_hsk != nivel:
                caracter.nivel_hsk = nivel
                por_actualizar.append(caracter)

        if solo_revisar:
            self.stdout.write(f"Cambiarían de nivel: {len(por_actualizar)}")
            for c in por_actualizar[:20]:
                self.stdout.write(f"  {c.hanzi} -> HSK{c.nivel_hsk}")
            if len(por_actualizar) > 20:
                self.stdout.write(f"  ... y {len(por_actualizar) - 20} más")
        else:
            with transaction.atomic():
                Caracter.objects.bulk_update(por_actualizar, ["nivel_hsk"], batch_size=500)

            self.stdout.write(self.style.SUCCESS(
                f"Actualizados: {len(por_actualizar)} caracteres."
            ))

        if faltantes:
            self.stdout.write(self.style.WARNING(
                f"En las listas pero no en la base ({len(faltantes)}): "
                f"{''.join(faltantes[:20])}"
            ))

        self._resumen()

    def _resumen(self):
        self.stdout.write("")
        self.stdout.write("Distribución actual:")

        for nivel in range(1, 7):
            cuenta = Caracter.objects.filter(nivel_hsk=nivel).count()
            self.stdout.write(f"  HSK{nivel}: {cuenta}")

        sin_nivel = Caracter.objects.filter(nivel_hsk__isnull=True).count()
        self.stdout.write(f"  Sin clasificar: {sin_nivel}")
