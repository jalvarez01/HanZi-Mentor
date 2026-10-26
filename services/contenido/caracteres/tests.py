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


class IdiomaDeLosMensajesTest(TestCase):
    """T21: Accept-Language elige el idioma del mensaje; las claves, el status
    y el resto del JSON no cambian. Sin cabecera, en español."""

    def setUp(self):
        self.client = APIClient()
        caracter = Caracter.objects.create(hanzi="人", pinyin="rén")
        Trazo.objects.create(caracter=caracter, secuencia=1, path_svg="", mediana=MEDIANA)

    def _validar(self, idioma, secuencia=1, puntos=None):
        puntos = puntos if puntos is not None else trazo_usuario(MEDIANA, semilla=7)
        return self.client.post(
            f"/api/caracteres/人/trazos/{secuencia}/validar/",
            {"puntos": puntos, "ancho": ANCHO, "alto": ALTO},
            format="json", HTTP_ACCEPT_LANGUAGE=idioma,
        )

    def test_caracter_inexistente_en_espanol_y_en_ingles(self):
        es = self.client.get("/api/caracteres/龘/", HTTP_ACCEPT_LANGUAGE="es")
        en = self.client.get("/api/caracteres/龘/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")

        self.assertEqual((es.status_code, en.status_code), (404, 404))
        self.assertEqual(es.json(), {"error": "Carácter no encontrado."})
        self.assertEqual(en.json(), {"error": "Character not found."})

    def test_sin_cabecera_o_con_otro_idioma_responde_en_espanol(self):
        sin = self.client.get("/api/caracteres/龘/")
        frances = self.client.get("/api/caracteres/龘/", HTTP_ACCEPT_LANGUAGE="fr")

        self.assertEqual(sin.json()["error"], "Carácter no encontrado.")
        self.assertEqual(frances.json()["error"], "Carácter no encontrado.")

    def test_trazo_inexistente_con_parametros(self):
        es = self._validar("es", secuencia=9)
        en = self._validar("en", secuencia=9)

        self.assertEqual(es.json()["error"], "El carácter '人' no tiene un trazo con secuencia 9.")
        self.assertEqual(en.json()["error"], "The character '人' has no stroke with sequence 9.")

    def test_el_detalle_del_veredicto_se_traduce(self):
        es = self._validar("es").json()
        en = self._validar("en").json()

        self.assertEqual(list(es), list(en))
        self.assertEqual(es["motivo"], en["motivo"])
        self.assertIn(es["detalle"], ("Trazo correcto.", "Trazo aceptable. Con más precisión quedaría perfecto."))
        self.assertIn(en["detalle"], ("Correct stroke.", "Acceptable stroke. With more precision it would be perfect."))

    def test_validacion_del_serializer_en_ingles(self):
        respuesta = self._validar("en", puntos=[[0, 0], "x"])

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("The point must be [x, y] or {'x': x, 'y': y}.", str(respuesta.json()))
