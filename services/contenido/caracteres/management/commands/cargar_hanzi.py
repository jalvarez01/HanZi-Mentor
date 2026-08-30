"""
Carga caracteres desde los archivos de Make Me a Hanzi.

Uso:
    python manage.py cargar_hanzi --ruta ../../datos/makemeahanzi --nivel 1 2

Espera encontrar `dictionary.txt` y `graphics.txt` en la ruta indicada.
Ambos son listas de objetos JSON separados por saltos de línea, en el mismo
orden, unibles por la clave 'character'.

Fuente: https://github.com/skishore/makemeahanzi (datos bajo licencias
Arphic y Unihan; ver el archivo COPYING del repositorio original).
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from caracteres.models import Caracter, Trazo
from caracteres.hsk import CARACTERES_POR_NIVEL


class Command(BaseCommand):
    help = "Importa caracteres y trazos desde los datos de Make Me a Hanzi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ruta",
            required=True,
            help="Carpeta que contiene dictionary.txt y graphics.txt.",
        )
        parser.add_argument(
            "--nivel",
            nargs="+",
            type=int,
            default=[1, 2],
            help="Niveles HSK a importar. Por defecto 1 y 2.",
        )
        parser.add_argument(
            "--todos",
            action="store_true",
            help=(
                "Importa TODOS los caracteres del archivo, no solo los de las "
                "listas HSK. Los que no estén en ninguna lista quedan con "
                "nivel_hsk vacío y se pueden clasificar después."
            ),
        )
        parser.add_argument(
            "--limpiar",
            action="store_true",
            help="Borra los caracteres existentes antes de importar.",
        )

    def handle(self, *args, **opciones):
        ruta = Path(opciones["ruta"])
        niveles = opciones["nivel"]

        archivo_dic = ruta / "dictionary.txt"
        archivo_graf = ruta / "graphics.txt"

        for archivo in (archivo_dic, archivo_graf):
            if not archivo.exists():
                raise CommandError(f"No se encontró {archivo}")

        # El nivel se asigna desde las listas HSK, existan o no en el filtro.
        nivel_de = {
            hanzi: nivel
            for nivel, caracteres in CARACTERES_POR_NIVEL.items()
            for hanzi in caracteres
        }

        if opciones["todos"]:
            deseados = None  # None = sin filtro
            self.stdout.write("Importando TODOS los caracteres del archivo...")
        else:
            deseados = set()
            for nivel in niveles:
                deseados.update(CARACTERES_POR_NIVEL.get(nivel, []))

            if not deseados:
                raise CommandError(
                    f"No hay caracteres definidos para los niveles {niveles}. "
                    f"Usá --todos para importar sin filtrar."
                )

            self.stdout.write(f"Buscando {len(deseados)} caracteres de HSK {niveles}...")

        definiciones = self._leer_filtrado(archivo_dic, deseados)
        graficos = self._leer_filtrado(archivo_graf, deseados)

        # Con --todos, el universo es lo que traiga el archivo.
        if deseados is None:
            deseados = set(definiciones) | set(graficos)
            self.stdout.write(f"Encontrados {len(deseados)} caracteres en la fuente.")

        with transaction.atomic():
            if opciones["limpiar"]:
                borrados = Caracter.objects.all().delete()[0]
                self.stdout.write(f"Borrados {borrados} registros previos.")

            creados, actualizados, sin_datos = 0, 0, []

            for hanzi in sorted(deseados):
                dic = definiciones.get(hanzi)
                graf = graficos.get(hanzi)

                if dic is None and graf is None:
                    sin_datos.append(hanzi)
                    continue

                caracter, fue_creado = Caracter.objects.update_or_create(
                    hanzi=hanzi,
                    defaults={
                        "pinyin": (dic or {}).get("pinyin", [""])[0] if (dic or {}).get("pinyin") else "",
                        "definicion": (dic or {}).get("definition") or "",
                        "radical": (dic or {}).get("radical") or "",
                        "descomposicion": (dic or {}).get("decomposition") or "",
                        "nivel_hsk": nivel_de.get(hanzi),
                    },
                )

                if graf:
                    caracter.trazos.all().delete()
                    trazos = graf.get("strokes", [])
                    medianas = graf.get("medians", [])

                    Trazo.objects.bulk_create([
                        Trazo(
                            caracter=caracter,
                            secuencia=i + 1,
                            path_svg=path,
                            mediana=medianas[i] if i < len(medianas) else [],
                        )
                        for i, path in enumerate(trazos)
                    ])

                creados += int(fue_creado)
                actualizados += int(not fue_creado)

            self.stdout.write(self.style.SUCCESS(
                f"Listo: {creados} creados, {actualizados} actualizados."
            ))

            con_nivel = Caracter.objects.filter(nivel_hsk__isnull=False).count()
            sin_nivel = Caracter.objects.filter(nivel_hsk__isnull=True).count()

            self.stdout.write(f"Con nivel HSK asignado: {con_nivel}")
            if sin_nivel:
                self.stdout.write(self.style.WARNING(
                    f"Sin clasificar: {sin_nivel} — se pueden asignar después "
                    f"ampliando caracteres/hsk.py y volviendo a correr el comando."
                ))

            if sin_datos:
                self.stdout.write(self.style.WARNING(
                    f"Sin datos en la fuente ({len(sin_datos)}): {''.join(sin_datos[:20])}"
                ))

    def _leer_filtrado(self, archivo, deseados):
        """
        Lee línea por línea y guarda los caracteres que interesan.

        Se procesa en streaming, sin cargar el archivo entero en memoria:
        graphics.txt pesa varios MB y crece con cada carácter.

        deseados=None significa quedarse con todos.
        """
        resultado = {}

        with archivo.open(encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue

                try:
                    dato = json.loads(linea)
                except json.JSONDecodeError:
                    continue

                hanzi = dato.get("character")
                if hanzi and (deseados is None or hanzi in deseados):
                    resultado[hanzi] = dato

        return resultado
