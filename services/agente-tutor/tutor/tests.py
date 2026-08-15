"""Los tests demuestran el valor de la inyección de dependencias:
el servicio se prueba sin tocar LangGraph ni enviar correos."""

import uuid

from django.test import TestCase

from .domain.builders import SesionEstudioBuilder
from .domain.exceptions import NivelNoPermitidoError, SesionInvalidaError
from .services import SesionEstudioService


class MotorFalso:
    def sugerir_dificultad(self, progreso):
        return 3

    def seleccionar_caracteres_nuevos(self, progreso, cantidad):
        return ["学", "校", "老", "师"][:cantidad]


class NotificadorEspia:
    def __init__(self):
        self.llamadas = []

    def sesion_lista(self, usuario_id, sesion):
        self.llamadas.append((usuario_id, sesion.pk))


class ProgresoFalso:
    def obtener(self, usuario_id):
        return {
            "nivel_hsk": 2,
            "nivel_max_desbloqueado": 2,
            "tasa_acierto": 0.7,
            "caracteres_dominados": [],
        }

    def caracteres_a_reforzar(self, usuario_id, limite=3):
        return ["目", "且"]


class SesionEstudioServiceTest(TestCase):
    def setUp(self):
        self.notificador = NotificadorEspia()
        self.service = SesionEstudioService(
            motor=MotorFalso(),
            notificador=self.notificador,
            progreso_repo=ProgresoFalso(),
        )
        self.usuario_id = uuid.uuid4()

    def test_crea_sesion_con_refuerzos_primero(self):
        sesion = self.service.crear_sesion_adaptativa(self.usuario_id, nivel_hsk=2)

        self.assertEqual(sesion.estado, "activa")
        self.assertEqual(sesion.total_ejercicios(), 6)
        self.assertTrue(sesion.ejercicios.filter(es_refuerzo=True).exists())

    def test_notifica_una_vez(self):
        self.service.crear_sesion_adaptativa(self.usuario_id, nivel_hsk=2)
        self.assertEqual(len(self.notificador.llamadas), 1)

    def test_rechaza_nivel_bloqueado(self):
        with self.assertRaises(NivelNoPermitidoError):
            self.service.crear_sesion_adaptativa(self.usuario_id, nivel_hsk=5)


class SesionEstudioBuilderTest(TestCase):
    def test_no_persiste_si_faltan_ejercicios(self):
        builder = (
            SesionEstudioBuilder()
            .para_usuario(uuid.uuid4(), nivel_max_desbloqueado=3)
            .en_nivel(1)
            .con_dificultad(2)
            .agregar_contenido_nuevo(["人"])
        )

        with self.assertRaises(SesionInvalidaError):
            builder.build()
