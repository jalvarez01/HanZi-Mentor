from django.test import TestCase
from rest_framework.test import APIClient

from caracteres.models import Caracter

from .models import Ejercicio, Leccion


class LeccionGenerarContenidoTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        for hanzi, pinyin, definicion in [
            ("你", "ni3", "tú"),
            ("好", "hao3", "bueno"),
            ("我", "wo3", "yo"),
        ]:
            Caracter.objects.create(
                hanzi=hanzi, pinyin=pinyin, definicion=definicion, nivel_hsk=1
            )

    def test_generar_contenido_crea_ejercicios_del_nivel(self):
        """La entidad Leccion organiza Caracter y Ejercicio vía generarContenido()."""
        leccion = Leccion.objects.create(usuario_id=1, nivel_hsk=1)
        ejercicios = leccion.generarContenido(cantidad=5)

        self.assertGreater(len(ejercicios), 0)
        self.assertEqual(Ejercicio.objects.filter(leccion=leccion).count(), len(ejercicios))
        for ejercicio in ejercicios:
            self.assertIn(ejercicio.tipo, ["trazo", "significado"])
            self.assertEqual(ejercicio.caracter.nivel_hsk, 1)

    def test_endpoint_generar_leccion_devuelve_201(self):
        respuesta = self.client.post(
            "/api/lecciones/generar/",
            {"usuario_id": 1, "nivel_hsk": 1, "cantidad": 5},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        self.assertTrue(len(respuesta.data["ejercicios"]) > 0)

    def test_endpoint_generar_leccion_nivel_invalido_devuelve_400(self):
        respuesta = self.client.post(
            "/api/lecciones/generar/",
            {"usuario_id": 1, "nivel_hsk": 9},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_endpoint_detalle_leccion_inexistente_devuelve_404(self):
        respuesta = self.client.get("/api/lecciones/9999/")
        self.assertEqual(respuesta.status_code, 404)

    def test_endpoint_detalle_leccion_devuelve_200(self):
        leccion = Leccion.objects.create(usuario_id=1, nivel_hsk=1)
        leccion.generarContenido(cantidad=5)

        respuesta = self.client.get(f"/api/lecciones/{leccion.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["id"], leccion.id)