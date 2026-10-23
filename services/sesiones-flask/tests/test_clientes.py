"""clientes.py: timeout, reintentos y respuestas degradadas."""

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from clientes import (
    CatalogoLocal,
    CatalogoRemoto,
    ClienteHttp,
    ProgresoRemoto,
    ServicioNoDisponible,
    progreso_inicial,
)

USUARIO = uuid.UUID("12345678-1234-5678-1234-567812345678")


class TransporteFalso:
    """Devuelve las respuestas en orden y anota cada llamada."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def __call__(self, metodo, url, cuerpo, timeout):
        self.llamadas.append((metodo, url, cuerpo, timeout))
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        estado, datos = respuesta
        return estado, datos if isinstance(datos, str) else json.dumps(datos)


def cliente(transporte, reintentos=2):
    esperas = []
    c = ClienteHttp("http://servicio:5000/", timeout=1.5, reintentos=reintentos,
                    espera=0.2, transporte=transporte, dormir=esperas.append)
    return c, esperas


# ---------- ClienteHttp ----------


def test_get_arma_la_url_y_usa_el_timeout():
    transporte = TransporteFalso((200, {"ok": True}))
    c, _ = cliente(transporte)

    assert c.get("/api/v2/caracteres/", {"nivel": 1, "excluir": "人,大"}) == {"ok": True}
    metodo, url, cuerpo, timeout = transporte.llamadas[0]
    assert (metodo, cuerpo, timeout) == ("GET", None, 1.5)
    assert url == "http://servicio:5000/api/v2/caracteres/?nivel=1&excluir=%E4%BA%BA%2C%E5%A4%A7"


def test_get_reintenta_errores_de_red_y_5xx_con_espera_creciente():
    transporte = TransporteFalso(ConnectionRefusedError("rechazada"), (503, {"error": "x"}), (200, {"ok": 1}))
    c, esperas = cliente(transporte)

    assert c.get("/x") == {"ok": 1}
    assert len(transporte.llamadas) == 3
    assert esperas == [0.2, 0.4]


def test_get_se_rinde_despues_de_los_reintentos():
    transporte = TransporteFalso(*[TimeoutError("lento")] * 3)
    c, esperas = cliente(transporte)

    with pytest.raises(ServicioNoDisponible):
        c.get("/x")
    assert len(transporte.llamadas) == 3
    assert len(esperas) == 2


def test_get_no_reintenta_un_4xx():
    transporte = TransporteFalso((400, {"error": "mal"}))
    c, esperas = cliente(transporte)

    with pytest.raises(ServicioNoDisponible) as error:
        c.get("/x")
    assert error.value.estado == 400
    assert len(transporte.llamadas) == 1
    assert esperas == []


def test_respuesta_html_cuenta_como_falla():
    transporte = TransporteFalso((200, "<html>proxy caido</html>"), (200, "<html></html>"), (200, "<html></html>"))
    c, _ = cliente(transporte)

    with pytest.raises(ServicioNoDisponible, match="no es JSON"):
        c.get("/x")


def test_post_no_se_reintenta():
    transporte = TransporteFalso(ConnectionRefusedError("rechazada"), (200, {}))
    c, _ = cliente(transporte)

    with pytest.raises(ServicioNoDisponible):
        c.post("/x", {"a": 1})
    assert len(transporte.llamadas) == 1
    assert json.loads(transporte.llamadas[0][2]) == {"a": 1}


# ---------- timeout real contra un servidor lento ----------


class Lento(BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(1)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args):
        pass


@pytest.fixture
def servidor_lento():
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Lento)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()
    servidor.server_close()


def test_timeout_real_corta_la_espera(servidor_lento):
    c = ClienteHttp(servidor_lento, timeout=0.2, reintentos=1, espera=0)
    inicio = time.monotonic()

    with pytest.raises(ServicioNoDisponible):
        c.get("/lento")
    # Dos intentos de 0.2 s, muy lejos del segundo que tarda el servidor.
    assert time.monotonic() - inicio < 0.9


def test_servicio_apagado_falla_rapido():
    # Puerto 1: nadie escucha.
    c = ClienteHttp("http://127.0.0.1:1", timeout=1, reintentos=0)

    with pytest.raises(ServicioNoDisponible):
        c.get("/x")


# ---------- respuestas degradadas ----------


def test_catalogo_remoto_usa_los_hanzi_del_servicio():
    transporte = TransporteFalso((200, {"caracteres": [{"hanzi": "人"}, {"hanzi": "大"}]}))
    catalogo = CatalogoRemoto(cliente(transporte)[0])

    assert catalogo.caracteres_de_nivel(1, excluir=["口"], cantidad=2) == ["人", "大"]
    assert "limite=2" in transporte.llamadas[0][1]


def test_catalogo_caido_usa_la_lista_local_sin_los_excluidos():
    transporte = TransporteFalso(*[ConnectionRefusedError()] * 3)
    catalogo = CatalogoRemoto(cliente(transporte)[0])

    assert catalogo.caracteres_de_nivel(2, excluir=["学"], cantidad=3) == ["校", "老", "师"]


def test_catalogo_vacio_usa_la_lista_local():
    catalogo = CatalogoRemoto(cliente(TransporteFalso((200, {"caracteres": []})))[0])

    assert catalogo.caracteres_de_nivel(1, cantidad=2) == ["人", "口"]


def test_catalogo_local_respeta_cantidad_y_nivel_desconocido():
    assert CatalogoLocal().caracteres_de_nivel(9) == []
    assert len(CatalogoLocal().caracteres_de_nivel(1, cantidad=4)) == 4


def test_progreso_caido_devuelve_valores_iniciales():
    progreso = ProgresoRemoto(cliente(TransporteFalso(*[TimeoutError()] * 3))[0])

    assert progreso.obtener(USUARIO) == progreso_inicial(USUARIO)


def test_refuerzos_caidos_devuelve_lista_vacia():
    progreso = ProgresoRemoto(cliente(TransporteFalso(*[(500, "{}")] * 3))[0])

    assert progreso.caracteres_a_reforzar(USUARIO) == []


def test_refuerzos_respeta_el_limite():
    transporte = TransporteFalso((200, {"caracteres": ["目", "且", "人"]}))
    progreso = ProgresoRemoto(cliente(transporte)[0])

    assert progreso.caracteres_a_reforzar(USUARIO, limite=2) == ["目", "且"]
    assert transporte.llamadas[0][1].endswith(f"/api/v2/progreso/{USUARIO}/refuerzos/?limite=2")


def test_registrar_respuesta_caido_devuelve_none():
    progreso = ProgresoRemoto(cliente(TransporteFalso(ConnectionRefusedError()))[0])

    assert progreso.registrar_respuesta(USUARIO, "学", True) is None


def test_registrar_respuesta_manda_el_cuerpo_esperado():
    transporte = TransporteFalso((200, {"tasa_acierto": 0.55}))
    progreso = ProgresoRemoto(cliente(transporte)[0])

    assert progreso.registrar_respuesta(USUARIO, "学", True) == {"tasa_acierto": 0.55}
    metodo, url, cuerpo, _ = transporte.llamadas[0]
    assert metodo == "POST"
    assert url.endswith(f"/api/v2/progreso/{USUARIO}/respuestas/")
    assert json.loads(cuerpo) == {"caracter": "学", "acerto": True}
