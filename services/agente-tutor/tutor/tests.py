"""Los tests demuestran el valor de la inyección de dependencias:
el servicio se prueba sin tocar LangGraph ni enviar correos."""

import uuid

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .domain import sesion_logic
from .domain.builders import SesionEstudioBuilder
from .domain.exceptions import (
    EjercicioNoEncontradoError,
    NivelNoPermitidoError,
    SesionInvalidaError,
)
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


import os
from unittest import mock

import requests

from .infra.factories import CatalogoFactory

CATALOGO = "http://flask_catalogo:5000"
CONTENIDO = "http://contenido:8002"


def _respuesta(datos=None, estado=200):
    """Respuesta HTTP falsa con la interfaz de requests que usa CatalogoRemoto."""
    respuesta = mock.Mock(status_code=estado)
    respuesta.json.return_value = datos
    if estado >= 400:
        respuesta.raise_for_status.side_effect = requests.HTTPError(f"{estado}")
    return respuesta


class CatalogoRemotoRutasTest(TestCase):
    """Listado y detalle van a catalogo-flask (v2); los trazos, a contenido (v1)."""

    def setUp(self):
        self.catalogo = CatalogoRemoto(base_url=CATALOGO + "/", contenido_url=CONTENIDO)

    @mock.patch("requests.get")
    def test_el_listado_usa_la_ruta_v2_del_catalogo(self, get):
        get.return_value = _respuesta({"caracteres": [{"hanzi": "学"}, {"hanzi": "校"}]})

        resultado = self.catalogo.caracteres_de_nivel(2, excluir=["老"], cantidad=2)

        self.assertEqual(resultado, ["学", "校"])
        url = get.call_args.args[0]
        self.assertEqual(url, f"{CATALOGO}/api/v2/caracteres/")
        self.assertEqual(
            get.call_args.kwargs["params"], {"nivel": 2, "excluir": "老", "limite": 2}
        )

    @mock.patch("requests.get")
    def test_el_detalle_usa_la_ruta_v2_del_catalogo(self, get):
        get.return_value = _respuesta({"hanzi": "学", "pinyin": "xué"})

        detalle = self.catalogo.obtener_detalle("学")

        self.assertEqual(detalle["pinyin"], "xué")
        self.assertEqual(get.call_args.args[0], f"{CATALOGO}/api/v2/caracteres/学/")

    @mock.patch("requests.post")
    def test_comparar_trazo_usa_contenido_v1(self, post):
        post.return_value = _respuesta({"aprobado": True, "puntaje": 90})

        resultado = self.catalogo.comparar_trazo("学", 1, [[0, 0], [1, 1]], 300, 300)

        self.assertTrue(resultado["aprobado"])
        self.assertEqual(
            post.call_args.args[0], f"{CONTENIDO}/api/caracteres/学/trazos/1/validar/"
        )

    @mock.patch("requests.post")
    def test_sin_contenido_url_los_trazos_usan_base_url(self, post):
        post.return_value = _respuesta({"aprobado": True})

        CatalogoRemoto(base_url=CATALOGO).comparar_trazo("学", 1, [[0, 0], [1, 1]], 300, 300)

        self.assertEqual(
            post.call_args.args[0], f"{CATALOGO}/api/caracteres/学/trazos/1/validar/"
        )


class CatalogoRemotoRespaldoTest(TestCase):
    """Si el catálogo falla, el estudiante igual recibe caracteres del local."""

    def setUp(self):
        self.catalogo = CatalogoRemoto(base_url=CATALOGO, contenido_url=CONTENIDO)
        self.esperado = CatalogoLocal().caracteres_de_nivel(1, [], 3)

    @mock.patch("requests.get")
    def test_cae_al_local_si_el_catalogo_responde_error(self, get):
        get.return_value = _respuesta({"error": "x", "codigo": "SERVICIO_NO_DISPONIBLE"}, 502)

        self.assertEqual(self.catalogo.caracteres_de_nivel(1, cantidad=3), self.esperado)

    @mock.patch("requests.get", side_effect=requests.ConnectionError("rechazada"))
    def test_cae_al_local_si_el_catalogo_no_responde(self, get):
        self.assertEqual(self.catalogo.caracteres_de_nivel(1, cantidad=3), self.esperado)

    @mock.patch("requests.get")
    def test_cae_al_local_si_el_catalogo_viene_vacio(self, get):
        get.return_value = _respuesta({"caracteres": []})

        self.assertEqual(self.catalogo.caracteres_de_nivel(1, cantidad=3), self.esperado)

    @mock.patch("requests.get", side_effect=requests.Timeout("lento"))
    def test_el_detalle_devuelve_vacio_si_el_catalogo_falla(self, get):
        self.assertEqual(self.catalogo.obtener_detalle("学"), {})


class CatalogoConfiguracionTest(TestCase):
    """CATALOGO_URL y CONTENIDO_URL llegan a CatalogoRemoto desde el entorno."""

    @mock.patch.dict(
        os.environ,
        {"CATALOGO": "REMOTO", "CATALOGO_URL": CATALOGO, "CONTENIDO_URL": CONTENIDO},
    )
    def test_la_factory_lee_las_dos_urls(self):
        catalogo = CatalogoFactory.crear()

        self.assertIsInstance(catalogo, CatalogoRemoto)
        self.assertEqual(catalogo._base_url, CATALOGO)
        self.assertEqual(catalogo._contenido_url, CONTENIDO)

    @mock.patch.dict(os.environ, {"CATALOGO": "REMOTO"})
    def test_la_factory_usa_los_valores_por_defecto(self):
        os.environ.pop("CATALOGO_URL", None)
        os.environ.pop("CONTENIDO_URL", None)

        catalogo = CatalogoFactory.crear()

        self.assertEqual(catalogo._base_url, "http://localhost:5000")
        self.assertEqual(catalogo._contenido_url, "http://localhost:8002")


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


# ---------------------------------------------------------------------------
# Evaluación de respuestas
# ---------------------------------------------------------------------------

from .domain.evaluacion_logic import evaluar_respuesta
from .services import EvaluarEjercicioService


class EvaluarRespuestaPinyinTest(TestCase):
    def test_coincide_con_diacriticos(self):
        self.assertTrue(
            evaluar_respuesta("pinyin", 3, "xué", {"pinyin": "xué"})
        )

    def test_coincide_sin_diacriticos(self):
        self.assertTrue(
            evaluar_respuesta("pinyin", 3, "xue", {"pinyin": "xué"})
        )

    def test_no_coincide(self):
        self.assertFalse(
            evaluar_respuesta("pinyin", 3, "xiao", {"pinyin": "xué"})
        )


class EvaluarRespuestaSignificadoTest(TestCase):
    def test_coincide_exacto(self):
        self.assertTrue(
            evaluar_respuesta(
                "significado", 3, "study, learning",
                {"definicion": "study, learning"},
            )
        )

    def test_coincide_con_orden_de_palabras_distinto(self):
        self.assertTrue(
            evaluar_respuesta(
                "significado", 3, "learning, study",
                {"definicion": "study, learning"},
            )
        )

    def test_no_coincide(self):
        self.assertFalse(
            evaluar_respuesta(
                "significado", 3, "mountain",
                {"definicion": "study, learning"},
            )
        )

    def test_pasa_en_dificultad_baja_pero_falla_en_dificultad_alta(self):
        respuesta = "aprendio"  # similar pero no idéntico a la definición
        datos = {"definicion": "aprender"}

        self.assertTrue(evaluar_respuesta("significado", 1, respuesta, datos))
        self.assertFalse(evaluar_respuesta("significado", 5, respuesta, datos))


class EvaluarRespuestaTrazoTest(TestCase):
    def setUp(self):
        self.sesion = SesionEstudio.objects.create(
            usuario_id=uuid.uuid4(), nivel_hsk=2, dificultad=3, estado="activa"
        )
        self.ejercicio = Ejercicio.objects.create(
            sesion=self.sesion, caracter="学", tipo="trazo", dificultad=3
        )

    def test_evalua_trazo_delegando_en_catalogo_remoto(self):
        catalogo_falso = type("CatalogoFalso", (), {
            "comparar_trazo": lambda self, hanzi, secuencia, puntos, ancho, alto: {
                "aprobado": True,
                "puntaje": 92,
                "motivo": "ok",
                "invertido": False,
                "detalle": "",
                "distancia_media": 3.2,
                "razon_longitud": 1.0,
                "puntos_lejanos": [],
            },
        })()

        service = EvaluarEjercicioService(catalogo=catalogo_falso)
        resultado = service.evaluar(
            self.ejercicio.pk,
            {"secuencia": 1, "puntos": [[0, 0], [1, 1]], "ancho": 320, "alto": 320},
        )

        self.assertTrue(resultado["aprobado"])
        self.assertEqual(resultado["puntaje"], 92)

    def test_sin_secuencia_lanza_value_error(self):
        catalogo_falso = type("CatalogoFalso", (), {
            "comparar_trazo": lambda self, hanzi, secuencia, puntos, ancho, alto: {},
        })()

        service = EvaluarEjercicioService(catalogo=catalogo_falso)

        with self.assertRaises(ValueError):
            service.evaluar(
                self.ejercicio.pk,
                {"puntos": [[0, 0], [1, 1]], "ancho": 320, "alto": 320},
            )


class EvaluarRespuestaCasosInvalidosTest(TestCase):
    def test_dificultad_fuera_de_rango_lanza_value_error(self):
        with self.assertRaises(ValueError):
            evaluar_respuesta("significado", 6, "algo", {"definicion": "algo"})

    def test_tipo_desconocido_lanza_value_error(self):
        with self.assertRaises(ValueError):
            evaluar_respuesta("audio", 3, "algo", {})


class EvaluarEjercicioServiceTest(TestCase):
    def setUp(self):
        self.sesion = SesionEstudio.objects.create(
            usuario_id=uuid.uuid4(), nivel_hsk=2, dificultad=3, estado="activa"
        )

    def test_evalua_pinyin_correctamente(self):
        ejercicio = Ejercicio.objects.create(
            sesion=self.sesion, caracter="学", tipo="pinyin", dificultad=3
        )
        catalogo_falso = type("CatalogoFalso", (), {
            "obtener_detalle": lambda self, hanzi: {"pinyin": "xué"},
        })()

        service = EvaluarEjercicioService(catalogo=catalogo_falso)
        resultado = service.evaluar(ejercicio.pk, "xue")

        self.assertTrue(resultado)

    def test_evalua_significado_incorrectamente(self):
        ejercicio = Ejercicio.objects.create(
            sesion=self.sesion, caracter="学", tipo="significado", dificultad=3
        )
        catalogo_falso = type("CatalogoFalso", (), {
            "obtener_detalle": lambda self, hanzi: {"definicion": "study, learning"},
        })()

        service = EvaluarEjercicioService(catalogo=catalogo_falso)
        resultado = service.evaluar(ejercicio.pk, "mountain")

        self.assertFalse(resultado)

    def test_evalua_trazo_devuelve_resultado_completo(self):
        ejercicio = Ejercicio.objects.create(
            sesion=self.sesion, caracter="学", tipo="trazo", dificultad=3
        )
        catalogo_falso = type("CatalogoFalso", (), {
            "comparar_trazo": lambda self, hanzi, secuencia, puntos, ancho, alto: {
                "aprobado": False,
                "puntaje": 40,
                "motivo": "forma_distinta",
                "invertido": True,
                "detalle": "trazo invertido",
                "distancia_media": 15.4,
                "razon_longitud": 0.6,
                "puntos_lejanos": [[10, 10]],
            },
        })()

        service = EvaluarEjercicioService(catalogo=catalogo_falso)
        resultado = service.evaluar(
            ejercicio.pk,
            {"secuencia": 2, "puntos": [[0, 0], [5, 5]], "ancho": 320, "alto": 320},
        )

        self.assertFalse(resultado["aprobado"])
        self.assertEqual(resultado["motivo"], "forma_distinta")
        self.assertTrue(resultado["invertido"])

    def test_evaluar_ejercicio_inexistente_lanza_error_de_dominio(self):
        """No debe dejar escapar Ejercicio.DoesNotExist crudo del ORM."""
        catalogo_falso = type("CatalogoFalso", (), {})()
        service = EvaluarEjercicioService(catalogo=catalogo_falso)

        with self.assertRaises(EjercicioNoEncontradoError):
            service.evaluar(999999, "cualquier respuesta")

    @mock.patch.dict(os.environ, {"CATALOGO_URL": CATALOGO, "CONTENIDO_URL": CONTENIDO})
    def test_el_catalogo_por_defecto_lee_las_dos_urls(self):
        catalogo = EvaluarEjercicioService()._catalogo

        self.assertEqual(catalogo._base_url, CATALOGO)
        self.assertEqual(catalogo._contenido_url, CONTENIDO)


# ---------------------------------------------------------------------------
# Idioma de los mensajes (T21)
# ---------------------------------------------------------------------------


class IdiomaDeLosMensajesTest(APITestCase):
    """Accept-Language elige el idioma del mensaje; las claves y el status no
    cambian. Sin cabecera, o con un idioma que no está, en español."""

    def setUp(self):
        sesion = SesionEstudio.objects.create(
            usuario_id=uuid.uuid4(), nivel_hsk=2, dificultad=3, estado="activa"
        )
        self.ejercicio = Ejercicio.objects.create(
            sesion=sesion, caracter="学", tipo="trazo", dificultad=3
        )
        self.url = reverse("responder-ejercicio", kwargs={"ejercicio_id": self.ejercicio.pk})

    def test_sesion_inexistente_en_espanol_y_en_ingles(self):
        url = reverse("detalle-sesion", kwargs={"sesion_id": 9999})

        es = self.client.get(url, HTTP_ACCEPT_LANGUAGE="es")
        en = self.client.get(url, HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")
        fr = self.client.get(url, HTTP_ACCEPT_LANGUAGE="fr")

        self.assertEqual({es.status_code, en.status_code, fr.status_code}, {404})
        self.assertEqual(es.json(), {"error": "Sesión no encontrada."})
        self.assertEqual(en.json(), {"error": "Session not found."})
        self.assertEqual(fr.json(), {"error": "Sesión no encontrada."})

    def test_ejercicio_ya_respondido_con_parametro(self):
        self.client.post(self.url, {"acerto": True}, format="json")

        es = self.client.post(self.url, {"acerto": True}, format="json", HTTP_ACCEPT_LANGUAGE="es")
        en = self.client.post(self.url, {"acerto": True}, format="json", HTTP_ACCEPT_LANGUAGE="en")

        self.assertEqual((es.status_code, en.status_code), (409, 409))
        self.assertEqual(es.json()["error"], f"El ejercicio {self.ejercicio.pk} ya fue respondido.")
        self.assertEqual(en.json()["error"], f"Exercise {self.ejercicio.pk} has already been answered.")

    def test_mensajes_de_drf_tambien_siguen_el_idioma(self):
        es = self.client.post(self.url, {}, format="json", HTTP_ACCEPT_LANGUAGE="es")
        en = self.client.post(self.url, {}, format="json", HTTP_ACCEPT_LANGUAGE="en")

        self.assertEqual(list(es.json()), ["acerto"])
        self.assertEqual(list(en.json()), ["acerto"])
        self.assertEqual(en.json()["acerto"], ["This field is required."])
        self.assertNotEqual(es.json()["acerto"], en.json()["acerto"])

    def test_reglas_del_builder_en_ingles(self):
        from django.utils import translation

        builder = (
            SesionEstudioBuilder()
            .para_usuario(uuid.uuid4(), nivel_max_desbloqueado=1)
            .en_nivel(3)
        )
        with translation.override("en"):
            with self.assertRaises(NivelNoPermitidoError) as error:
                builder.con_dificultad(2).build()

        self.assertEqual(str(error.exception), "HSK3 is not unlocked yet (current maximum: HSK1).")
