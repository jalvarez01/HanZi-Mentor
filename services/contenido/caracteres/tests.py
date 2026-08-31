from django.test import TestCase
from rest_framework.test import APIClient

from .models import Caracter, Trazo
from .tests_comparador import a_canvas, densificar, trazo_usuario

MEDIANA = [[458, 800], [435, 764], [400, 700], [350, 620], [300, 540]]
ANCHO = ALTO = 300


class ValidarTrazoAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.caracter = Caracter.objects.create(hanzi="人", pinyin="rén")
        self.trazo = Trazo.objects.create(
            caracter=self.caracter, secuencia=1,
            path_svg="", mediana=MEDIANA,
        )

    def _url(self, hanzi="人", secuencia=1):
        return f"/api/caracteres/{hanzi}/trazos/{secuencia}/validar/"

    def test_trazo_correcto_devuelve_200_con_aprobado_true(self):
        puntos = trazo_usuario(MEDIANA, semilla=7)
        respuesta = self.client.post(
            self._url(), {"puntos": puntos, "ancho": ANCHO, "alto": ALTO},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.data["aprobado"])

    def test_trazo_invertido_devuelve_200_con_motivo_invertido(self):
        puntos = trazo_usuario(MEDIANA, semilla=7, invertir=True)
        respuesta = self.client.post(
            self._url(), {"puntos": puntos, "ancho": ANCHO, "alto": ALTO},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["motivo"], "invertido")

    def test_caracter_inexistente_devuelve_404(self):
        puntos = trazo_usuario(MEDIANA, semilla=7)
        respuesta = self.client.post(
            self._url(hanzi="不"), {"puntos": puntos, "ancho": ANCHO, "alto": ALTO},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_secuencia_inexistente_devuelve_404(self):
        puntos = trazo_usuario(MEDIANA, semilla=7)
        respuesta = self.client.post(
            self._url(secuencia=9), {"puntos": puntos, "ancho": ANCHO, "alto": ALTO},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_cuerpo_sin_puntos_devuelve_400(self):
        respuesta = self.client.post(
            self._url(), {"ancho": ANCHO, "alto": ALTO},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
