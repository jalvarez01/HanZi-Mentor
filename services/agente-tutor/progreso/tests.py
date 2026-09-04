from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import ProgresoUsuario


class ConsultarProgresoViewTest(APITestCase):
	def setUp(self):
		self.usuario_id = "12345678-1234-5678-1234-567812345678"
		self.url = reverse("consultar-progreso", kwargs={"usuario_id": self.usuario_id})

	def test_devuelve_valores_iniciales_sin_persistir_progreso(self):
		respuesta = self.client.get(self.url)

		self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
		self.assertEqual(respuesta.data["usuario_id"], self.usuario_id)
		self.assertEqual(respuesta.data["nivel_hsk"], 1)
		self.assertEqual(respuesta.data["nivel_max_desbloqueado"], 1)
		self.assertEqual(respuesta.data["tasa_acierto"], 0.5)
		self.assertEqual(respuesta.data["caracteres_dominados"], [])
		self.assertEqual(respuesta.data["errores_frecuentes"], {})
		self.assertEqual(respuesta.data["aciertos_consecutivos"], {})
		self.assertIsNone(respuesta.data["proximo_repaso"])
		self.assertIsNone(respuesta.data["actualizado_en"])
		self.assertEqual(respuesta.data["total_dominados"], 0)
		self.assertEqual(respuesta.data["total_por_reforzar"], 0)
		self.assertEqual(respuesta.data["caracteres_debiles"], [])
		self.assertFalse(ProgresoUsuario.objects.filter(usuario_id=self.usuario_id).exists())

	def test_devuelve_el_resumen_completo_del_progreso_existente(self):
		ProgresoUsuario.objects.create(
			usuario_id=self.usuario_id,
			nivel_hsk=2,
			nivel_max_desbloqueado=3,
			tasa_acierto=0.75,
			caracteres_dominados=["学", "校"],
			errores_frecuentes={"目": 2, "人": 5, "且": 3},
			aciertos_consecutivos={"学": 4},
		)

		respuesta = self.client.get(self.url)

		self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
		self.assertEqual(respuesta.data["total_dominados"], 2)
		self.assertEqual(respuesta.data["total_por_reforzar"], 3)
		self.assertEqual(
			respuesta.data["caracteres_debiles"],
			[
				{"caracter": "人", "fallos": 5},
				{"caracter": "且", "fallos": 3},
				{"caracter": "目", "fallos": 2},
			],
		)
