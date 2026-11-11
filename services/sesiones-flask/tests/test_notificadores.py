"""NotificadorCola: publica por nombre y nunca rompe ni demora la creación de la sesión."""

import threading
import time

from kombu.exceptions import OperationalError

import notificadores
from app import create_app
from fabricas import Dependencias
from modelos import SesionEstudio
from notificadores import NotificadorCola, crear_publicador
from tests.conftest import USUARIO, MotorFalso, ProgresoFalso
from tests.test_sesiones import contar


class PublicadorEspia:
    def __init__(self, error=None, demora=0):
        self.error = error
        self.demora = demora
        self.enviadas = []

    def send_task(self, nombre, args=None, **opciones):
        time.sleep(self.demora)
        self.enviadas.append((nombre, args, opciones))
        if self.error:
            raise self.error


class PublicadorTrabado:
    """Se queda en la primera publicación hasta que la prueba lo suelte."""

    def __init__(self):
        self.entro = threading.Event()
        self.soltar = threading.Event()
        self.enviadas = []

    def send_task(self, nombre, args=None, **opciones):
        self.entro.set()
        self.soltar.wait(5)
        self.enviadas.append(args)


def crear_cliente(notificador):
    deps = Dependencias(motor=MotorFalso(), notificador=notificador, progreso=ProgresoFalso())
    app = create_app({"TESTING": True, "DATABASE_URL": "sqlite://"}, dependencias=deps)
    return app, app.test_client()


def crear(client):
    return client.post("/api/v2/sesiones/", json={"usuario_id": str(USUARIO), "nivel_hsk": 2})


def hilos_notificador():
    return [h for h in threading.enumerate() if h.name == "notificador-cola"]


# ---------------------------------------------------------------- publicación


def test_publica_por_nombre_con_usuario_y_sesion():
    publicador = PublicadorEspia()
    notificador = NotificadorCola(publicador)
    _, client = crear_cliente(notificador)

    resp = crear(client)
    notificador.esperar_pendientes()

    assert resp.status_code == 201
    assert publicador.enviadas == [
        ("notificar_sesion_lista", [str(USUARIO), resp.get_json()["id"]], {"ignore_result": True}),
    ]


def test_los_argumentos_son_json():
    # El worker solo acepta JSON: el UUID va como texto y el id como entero.
    publicador = PublicadorEspia()
    notificador = NotificadorCola(publicador)
    _, client = crear_cliente(notificador)

    crear(client)
    notificador.esperar_pendientes()

    [(_, (usuario_id, sesion_id), _)] = publicador.enviadas
    assert isinstance(usuario_id, str) and isinstance(sesion_id, int)


# ---------------------------------------------------------------- fallas


def test_broker_caido_no_rompe_crear_la_sesion(caplog):
    notificador = NotificadorCola(PublicadorEspia(OperationalError("Error 111 connecting to redis:6379")))
    app, client = crear_cliente(notificador)

    with caplog.at_level("WARNING"):
        resp = crear(client)
        notificador.esperar_pendientes()

    assert resp.status_code == 201
    assert "No se pudo publicar notificar_sesion_lista" in caplog.text
    sesion_db = app.extensions["db"]["fabrica"]()
    try:
        assert contar(sesion_db, SesionEstudio) == 1
    finally:
        sesion_db.close()


def test_cualquier_error_al_publicar_se_captura():
    notificador = NotificadorCola(PublicadorEspia(RuntimeError("inesperado")))
    _, client = crear_cliente(notificador)

    assert crear(client).status_code == 201
    notificador.esperar_pendientes()


def test_no_poder_crear_el_hilo_no_rompe_crear_la_sesion(monkeypatch, caplog):
    def fallar(self):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(NotificadorCola, "_asegurar_hilo", fallar)
    _, client = crear_cliente(NotificadorCola(PublicadorEspia()))

    with caplog.at_level("WARNING"):
        assert crear(client).status_code == 201
    assert "can't start new thread" in caplog.text


def test_cola_llena_descarta_con_aviso_y_la_sesion_sigue_en_201(caplog):
    publicador = PublicadorTrabado()
    notificador = NotificadorCola(publicador, maximo_pendientes=1)
    _, client = crear_cliente(notificador)

    with caplog.at_level("WARNING"):
        primera = crear(client)       # la toma el hilo y se traba
        assert publicador.entro.wait(5)
        segunda = crear(client)       # espera en la cola (1 de 1)
        tercera = crear(client)       # cola llena: se descarta

    assert [r.status_code for r in (primera, segunda, tercera)] == [201, 201, 201]
    assert "Cola de notificaciones llena (1 pendientes)" in caplog.text
    assert f"sesión {tercera.get_json()['id']}" in caplog.text

    publicador.soltar.set()
    notificador.esperar_pendientes()
    assert [args[1] for args in publicador.enviadas] == [
        primera.get_json()["id"], segunda.get_json()["id"],
    ]


def test_por_defecto_admite_100_pendientes():
    assert notificadores.MAXIMO_PENDIENTES == 100
    assert NotificadorCola(PublicadorEspia())._maximo_pendientes == 100


# ---------------------------------------------------------------- hilo


def test_el_hilo_se_crea_perezoso_y_una_sola_vez_por_proceso():
    antes = len(hilos_notificador())
    notificador = NotificadorCola(PublicadorEspia())
    _, client = crear_cliente(notificador)

    # Crear la app no arranca el hilo: en gunicorn sería antes de servir.
    assert notificador._hilo is None
    assert len(hilos_notificador()) == antes

    for _ in range(3):
        crear(client)
    notificador.esperar_pendientes()

    assert len(hilos_notificador()) == antes + 1
    assert notificador._hilo.daemon is True
    assert notificador._hilo.is_alive()


def test_otro_proceso_crea_su_propio_hilo(monkeypatch):
    # Simula un fork: el pid cambia y el hilo del padre no existe en el hijo.
    notificador = NotificadorCola(PublicadorEspia())
    _, client = crear_cliente(notificador)
    crear(client)
    hilo_padre, cola_padre = notificador._hilo, notificador._cola

    monkeypatch.setattr(notificadores.os, "getpid", lambda: -1)
    crear(client)
    notificador.esperar_pendientes()

    assert notificador._hilo is not hilo_padre
    assert notificador._cola is not cola_padre
    assert notificador._pid == -1


# ---------------------------------------------------------------- tiempos


def test_la_respuesta_no_espera_a_la_publicacion():
    # Redis lento o un DNS que tarda: la sesión responde sin esperar.
    publicador = PublicadorEspia(demora=3)
    notificador = NotificadorCola(publicador)
    _, client = crear_cliente(notificador)

    inicio = time.monotonic()
    resp = crear(client)
    duracion = time.monotonic() - inicio

    assert resp.status_code == 201
    assert duracion < 1
    notificador.esperar_pendientes()
    assert len(publicador.enviadas) == 1


def test_redis_real_apagado_responde_201_rapido(caplog):
    # Publicador de verdad contra un puerto cerrado.
    notificador = NotificadorCola(crear_publicador("redis://127.0.0.1:9/0", timeout=1.0))
    _, client = crear_cliente(notificador)

    inicio = time.monotonic()
    resp = crear(client)
    duracion = time.monotonic() - inicio

    assert resp.status_code == 201
    assert duracion < 1
    with caplog.at_level("WARNING"):
        notificador.esperar_pendientes()
    assert "No se pudo publicar" in caplog.text
