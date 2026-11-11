"""T22: Accept-Language elige el idioma del mensaje; las claves, el código y
el estado no cambian. Sin cabecera, o con otro idioma, en español.

`lang` sigue eligiendo el idioma de las traducciones de Tatoeba; la cabecera
solo cambia los mensajes de error."""

from dominio.puertos import ProveedorNoDisponible
from test_ejemplos import URL, cliente
from test_tatoeba import SIMPLIFICADA, adaptador

EN = {"Accept-Language": "en-US,en;q=0.9"}


def test_limite_invalido_en_espanol_y_en_ingles():
    c = cliente()

    es = c.get(URL.format("学") + "?limite=0")
    en = c.get(URL.format("学") + "?limite=0", headers=EN)

    assert (es.status_code, en.status_code) == (400, 400)
    assert es.get_json() == {"error": "El límite debe ser un entero entre 1 y 10", "codigo": "ENTRADA_INVALIDA"}
    assert en.get_json() == {"error": "The limit must be an integer between 1 and 10", "codigo": "ENTRADA_INVALIDA"}


def test_idioma_no_soportado_en_ingles():
    resp = cliente().get(URL.format("学") + "?lang=fr", headers=EN)

    assert resp.get_json()["error"] == "Unsupported language: use es, en"


def test_atribucion_de_tatoeba_en_el_idioma_de_la_peticion():
    tatoeba, _ = adaptador(respuesta={"data": [SIMPLIFICADA]})
    c = cliente(tatoeba)

    es = c.get(URL.format("学")).get_json()
    en = c.get(URL.format("学"), headers=EN).get_json()

    assert es["atribucion"] == "Oraciones de Tatoeba.org (CC BY 2.0 FR)"
    assert en["atribucion"] == "Sentences from Tatoeba.org (CC BY 2.0 FR)"


def test_proveedor_caido_en_ingles():
    class Caido:
        nombre = "caido"
        atribucion = None

        def obtener(self, hanzi, idioma, limite):
            raise ProveedorNoDisponible("sin red")

    resp = cliente(Caido()).get(URL.format("学"), headers=EN)

    assert resp.status_code == 503
    assert resp.get_json() == {
        "error": "The examples provider is not available",
        "codigo": "PROVEEDOR_NO_DISPONIBLE",
    }
