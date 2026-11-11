"""clientes.py: timeout, reintentos solo en GET y errores tipados."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from clientes import (
    CatalogoRemoto,
    ClienteHttp,
    RespuestaRechazada,
    ServicioNoDisponible,
    TrazosRemoto,
)


class TransporteFalso:
    """Devuelve las respuestas en orden y anota cada llamada."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []
        self.cabeceras = []

    def __call__(self, metodo, url, cuerpo, timeout, extra=None):
        self.llamadas.append((metodo, url, cuerpo, timeout))
        self.cabeceras.append(extra)
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

    assert c.get("/api/v2/caracteres/", {"nivel": 1}) == {"ok": True}
    metodo, url, cuerpo, timeout = transporte.llamadas[0]
    assert (metodo, cuerpo, timeout) == ("GET", None, 1.5)
    assert url == "http://servicio:5000/api/v2/caracteres/?nivel=1"


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


def test_un_4xx_es_respuesta_rechazada_con_su_json_y_no_se_reintenta():
    transporte = TransporteFalso((404, {"error": "No encontrado", "codigo": "NO_ENCONTRADO"}))
    c, esperas = cliente(transporte)

    with pytest.raises(RespuestaRechazada) as error:
        c.get("/x")
    assert error.value.estado == 404
    assert error.value.datos["codigo"] == "NO_ENCONTRADO"
    assert len(transporte.llamadas) == 1
    assert esperas == []


def test_un_4xx_sin_json_deja_datos_vacios():
    c, _ = cliente(TransporteFalso((404, "<html>no</html>")))

    with pytest.raises(RespuestaRechazada) as error:
        c.get("/x")
    assert error.value.datos == {}


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


def test_post_con_5xx_es_servicio_no_disponible():
    c, _ = cliente(TransporteFalso((502, {"error": "x"})))

    with pytest.raises(ServicioNoDisponible) as error:
        c.post("/x", {})
    assert error.value.estado == 502


# ---------- clientes de catálogo y trazos ----------


def test_catalogo_pide_el_detalle_con_el_hanzi_codificado():
    transporte = TransporteFalso((200, {"hanzi": "学", "pinyin": "xué"}))
    c, _ = cliente(transporte)

    assert CatalogoRemoto(c).obtener_detalle("学")["pinyin"] == "xué"
    assert transporte.llamadas[0][1] == "http://servicio:5000/api/v2/caracteres/%E5%AD%A6/"


def test_trazos_manda_mediana_puntos_y_lienzo():
    transporte = TransporteFalso((200, {"aprobado": True}))
    c, _ = cliente(transporte)

    resultado = TrazosRemoto(c).validar([[0, 0], [1, 1]], [[0, 0], [2, 2]], 300, 280)

    assert resultado == {"aprobado": True}
    metodo, url, cuerpo, _ = transporte.llamadas[0]
    assert (metodo, url) == ("POST", "http://servicio:5000/api/v2/trazos/validar/")
    assert json.loads(cuerpo) == {
        "mediana": [[0, 0], [1, 1]], "puntos": [[0, 0], [2, 2]], "ancho": 300, "alto": 280,
    }


# ---------- red real ----------


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


def test_puerto_cerrado_es_servicio_no_disponible():
    c = ClienteHttp("http://127.0.0.1:9", timeout=0.5, reintentos=0)

    with pytest.raises(ServicioNoDisponible):
        c.post("/api/v2/trazos/validar/", {})


# ---------- reenvío de Accept-Language ----------


def test_las_cabeceras_extra_van_en_get_y_post():
    transporte = TransporteFalso((200, {}), (200, {}))
    c = ClienteHttp("http://servicio:5000", transporte=transporte,
                    cabeceras=lambda: {"Accept-Language": "en-US,en;q=0.9"})

    c.get("/x")
    c.post("/y", {})

    assert transporte.cabeceras == [{"Accept-Language": "en-US,en;q=0.9"}] * 2


def test_sin_cabeceras_extra_no_manda_nada_de_mas():
    transporte = TransporteFalso((200, {}))

    ClienteHttp("http://servicio:5000", transporte=transporte).get("/x")

    assert transporte.cabeceras == [{}]
