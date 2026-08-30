"""Los tests demuestran el valor de la inyección de dependencias:
el servicio se prueba sin tocar LangGraph ni enviar correos."""

import uuid

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .domain import sesion_logic
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
        self.assertEqual(sesion_logic.total_ejercicios(sesion), 6)
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


# ---------------------------------------------------------------------------
# Repaso espaciado
# ---------------------------------------------------------------------------

from datetime import timedelta

from django.utils import timezone

from .domain import progreso_logic
from .domain.repaso import (
    actualizar_tasa_acierto,
    calcular_proximo_repaso,
    esta_pendiente,
)
from .models import Ejercicio, SesionEstudio
from .services import ResponderEjercicioService
from .domain.exceptions import EjercicioYaRespondidoError
from progreso.models import ProgresoUsuario


class RepasoEspaciadoTest(TestCase):
    def setUp(self):
        self.ahora = timezone.now()

    def test_el_intervalo_crece_con_la_racha(self):
        primero = calcular_proximo_repaso(0, acerto=True, desde=self.ahora)
        tercero = calcular_proximo_repaso(2, acerto=True, desde=self.ahora)

        self.assertEqual(primero, self.ahora + timedelta(days=1))
        self.assertEqual(tercero, self.ahora + timedelta(days=7))

    def test_fallar_acerca_el_repaso(self):
        tras_fallo = calcular_proximo_repaso(5, acerto=False, desde=self.ahora)
        self.assertEqual(tras_fallo, self.ahora + timedelta(hours=12))

    def test_el_intervalo_tiene_techo(self):
        muy_alto = calcular_proximo_repaso(99, acerto=True, desde=self.ahora)
        self.assertEqual(muy_alto, self.ahora + timedelta(days=90))

    def test_pendiente_si_nunca_se_agendo(self):
        self.assertTrue(esta_pendiente(None))
        self.assertFalse(esta_pendiente(self.ahora + timedelta(days=1), ahora=self.ahora))

    def test_la_tasa_sube_al_acertar_y_baja_al_fallar(self):
        self.assertGreater(actualizar_tasa_acierto(0.5, acerto=True), 0.5)
        self.assertLess(actualizar_tasa_acierto(0.5, acerto=False), 0.5)

    def test_la_tasa_nunca_sale_del_rango(self):
        self.assertLessEqual(actualizar_tasa_acierto(1.0, acerto=True), 1.0)
        self.assertGreaterEqual(actualizar_tasa_acierto(0.0, acerto=False), 0.0)


# ---------------------------------------------------------------------------
# Responder ejercicios
# ---------------------------------------------------------------------------


class ResponderEjercicioServiceTest(TestCase):
    def setUp(self):
        self.usuario_id = uuid.uuid4()
        self.sesion = SesionEstudio.objects.create(
            usuario_id=self.usuario_id, nivel_hsk=2, dificultad=3, estado="activa"
        )
        self.ejercicio = Ejercicio.objects.create(
            sesion=self.sesion, caracter="学", tipo="trazo", dificultad=3
        )
        self.otro = Ejercicio.objects.create(
            sesion=self.sesion, caracter="校", tipo="significado", dificultad=3
        )
        self.service = ResponderEjercicioService()

    def test_acertar_marca_el_ejercicio_y_agenda_repaso(self):
        resultado = self.service.responder(self.ejercicio.pk, acerto=True)

        self.ejercicio.refresh_from_db()
        self.assertTrue(self.ejercicio.respondido)
        self.assertTrue(self.ejercicio.fue_correcto)
        self.assertIsNotNone(resultado["proximo_repaso"])

    def test_fallar_suma_a_errores_frecuentes(self):
        self.service.responder(self.ejercicio.pk, acerto=False)

        progreso = ProgresoUsuario.objects.get(usuario_id=self.usuario_id)
        self.assertEqual(progreso.errores_frecuentes.get("学"), 1)
        self.assertEqual(progreso_logic.racha_de(progreso, "学"), 0)

    def test_acertar_corta_los_errores_y_suma_racha(self):
        self.service.responder(self.ejercicio.pk, acerto=True)

        progreso = ProgresoUsuario.objects.get(usuario_id=self.usuario_id)
        self.assertEqual(progreso_logic.racha_de(progreso, "学"), 1)
        self.assertIn("学", progreso.caracteres_dominados)

    def test_no_se_puede_responder_dos_veces(self):
        self.service.responder(self.ejercicio.pk, acerto=True)

        with self.assertRaises(EjercicioYaRespondidoError):
            self.service.responder(self.ejercicio.pk, acerto=False)

    def test_la_sesion_se_cierra_al_responder_todo(self):
        primero = self.service.responder(self.ejercicio.pk, acerto=True)
        self.assertFalse(primero["sesion_completada"])
        self.assertEqual(primero["pendientes"], 1)

        segundo = self.service.responder(self.otro.pk, acerto=True)
        self.assertTrue(segundo["sesion_completada"])

        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.estado, "completada")


class ResponderEjercicioViewTest(APITestCase):
    """A nivel HTTP: el código de estado es parte del contrato de la API."""

    def setUp(self):
        self.sesion = SesionEstudio.objects.create(
            usuario_id=uuid.uuid4(), nivel_hsk=2, dificultad=3, estado="activa"
        )
        self.ejercicio = Ejercicio.objects.create(
            sesion=self.sesion, caracter="学", tipo="trazo", dificultad=3
        )
        self.url = reverse(
            "responder-ejercicio", kwargs={"ejercicio_id": self.ejercicio.pk}
        )

    def test_responder_dos_veces_devuelve_409(self):
        self.client.post(self.url, {"acerto": True}, format="json")

        respuesta = self.client.post(self.url, {"acerto": True}, format="json")

        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)

    def test_ejercicio_inexistente_devuelve_404(self):
        url = reverse("responder-ejercicio", kwargs={"ejercicio_id": 9999})

        respuesta = self.client.post(url, {"acerto": True}, format="json")

        self.assertEqual(respuesta.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

from .infra.catalogo import CatalogoLocal, CatalogoRemoto


class CatalogoTest(TestCase):
    def test_el_local_excluye_los_dominados(self):
        catalogo = CatalogoLocal()
        resultado = catalogo.caracteres_de_nivel(2, excluir=["学", "校"], cantidad=3)

        self.assertNotIn("学", resultado)
        self.assertNotIn("校", resultado)
        self.assertEqual(len(resultado), 3)

    def test_el_remoto_cae_al_respaldo_si_falla_la_red(self):
        catalogo = CatalogoRemoto(base_url="http://no-existe-este-host:9999")
        resultado = catalogo.caracteres_de_nivel(1, cantidad=2)

        self.assertEqual(len(resultado), 2)


# ---------------------------------------------------------------------------
# Agente
# ---------------------------------------------------------------------------

from .agent.graph import construir_agente, nodo_analizar


class AgenteTest(TestCase):
    def test_el_analisis_resume_los_errores(self):
        estado = nodo_analizar({
            "progreso": {
                "nivel_hsk": 2,
                "tasa_acierto": 0.7,
                "caracteres_dominados": ["人"],
                "errores_frecuentes": {"目": 6, "且": 4},
            }
        })

        self.assertIn("HSK2", estado["resumen"])
        self.assertIn("目", estado["resumen"])

    def test_funciona_sin_credenciales(self):
        """Sin API key debe caer a la heurística, no reventar."""
        agente = construir_agente()

        resultado = agente.invoke({
            "tarea": "sugerir_dificultad",
            "progreso": {"tasa_acierto": 0.9, "nivel_hsk": 1},
        })

        self.assertEqual(resultado["dificultad"], 4)
