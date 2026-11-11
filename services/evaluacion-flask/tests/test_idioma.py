"""T22: Accept-Language elige el idioma del mensaje; las claves, el código y
el estado no cambian. Sin cabecera, o con otro idioma, en español.

El Accept-Language del usuario también se reenvía a catálogo y trazos, así
sus errores vuelven en ese idioma y evaluación los devuelve tal cual."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app import create_app
from conftest import CatalogoFalso, TrazosFalso
from fabricas import Dependencias

URL = "/api/v2/evaluacion/"
EN = {"Accept-Language": "en-US,en;q=0.9"}
TRAZO = {"secuencia": 1, "puntos": [[0, 0], [1, 1]], "ancho": 300, "alto": 300}


@pytest.mark.parametrize("cabeceras, mensaje", [
    ({}, "'tipo' debe ser uno de: pinyin, significado, trazo"),
    ({"Accept-Language": "es"}, "'tipo' debe ser uno de: pinyin, significado, trazo"),
    ({"Accept-Language": "fr"}, "'tipo' debe ser uno de: pinyin, significado, trazo"),
    (EN, "'tipo' must be one of: pinyin, significado, trazo"),
])
def test_validacion_en_el_idioma_pedido(evaluar_con, cabeceras, mensaje):
    resp = evaluar_con({"tipo": "audio", "caracter": "学", "respuesta": "x"}, cabeceras)

    assert resp.status_code == 400
    assert resp.get_json() == {"error": mensaje, "codigo": "ENTRADA_INVALIDA"}


def test_caracter_inexistente_con_parametro(evaluar_con):
    cuerpo = {"tipo": "pinyin", "caracter": "龘", "respuesta": "da"}

    es = evaluar_con(cuerpo, {"Accept-Language": "es"})
    en = evaluar_con(cuerpo, EN)

    assert (es.status_code, en.status_code) == (404, 404)
    assert es.get_json()["error"] == "No existe el carácter '龘'."
    assert en.get_json() == {"error": "The character '龘' does not exist.", "codigo": "NO_ENCONTRADO"}


def test_dependencia_caida_en_ingles():
    deps = Dependencias(catalogo=CatalogoFalso(), trazos=TrazosFalso(caido=True))
    client = create_app({"TESTING": True}, dependencias=deps).test_client()

    resp = client.post(URL, json={"tipo": "trazo", "caracter": "学", "respuesta": TRAZO}, headers=EN)

    assert resp.status_code == 503
    assert resp.get_json() == {
        "error": "The strokes service did not respond. Try again in a few seconds.",
        "codigo": "DEPENDENCIA_NO_DISPONIBLE",
    }


@pytest.fixture
def evaluar_con(client):
    def llamar(cuerpo, cabeceras):
        return client.post(URL, json=cuerpo, headers=cabeceras)

    return llamar


# ---------- reenvío real a catálogo y trazos ----------


class CatalogoYTrazos(BaseHTTPRequestHandler):
    """Hace de catalogo-flask y trazos-flask: anota el Accept-Language que
    recibe y responde el 400 de trazos en ese idioma."""

    recibidas = []

    def _json(self, estado, datos):
        cuerpo = json.dumps(datos).encode()
        self.send_response(estado)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        self.recibidas.append(("GET", self.headers.get("Accept-Language")))
        self._json(200, {"hanzi": "人", "trazos": [{"secuencia": 1, "mediana": [[0, 0], [9, 9]]}]})

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        idioma = self.headers.get("Accept-Language") or ""
        self.recibidas.append(("POST", idioma or None))
        mensaje = "'puntos' needs at least 2 points" if idioma.startswith("en") else "'puntos' necesita al menos 2 puntos"
        self._json(400, {"error": mensaje, "codigo": "ENTRADA_INVALIDA"})

    def log_message(self, *args):
        pass


@pytest.fixture
def servicios():
    CatalogoYTrazos.recibidas = []
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), CatalogoYTrazos)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()
    servidor.server_close()


def test_reenvia_accept_language_y_devuelve_el_error_de_trazos_tal_cual(servicios):
    app = create_app({"TESTING": True, "CATALOGO_URL": servicios, "TRAZOS_URL": servicios})
    cuerpo = {"tipo": "trazo", "caracter": "人", "respuesta": {**TRAZO, "puntos": [[0, 0]]}}

    en = app.test_client().post(URL, json=cuerpo, headers=EN)
    es = app.test_client().post(URL, json=cuerpo)

    assert en.status_code == 400
    assert en.get_json() == {"error": "'puntos' needs at least 2 points", "codigo": "ENTRADA_INVALIDA"}
    assert es.get_json()["error"] == "'puntos' necesita al menos 2 puntos"
    # Con cabecera se reenvía igual a los dos servicios; sin cabecera, no se inventa una.
    assert CatalogoYTrazos.recibidas == [
        ("GET", "en-US,en;q=0.9"), ("POST", "en-US,en;q=0.9"), ("GET", None), ("POST", None),
    ]
