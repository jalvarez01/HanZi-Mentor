"""Pruebas del endpoint de ejemplos y del patrón Adapter."""

import pytest

from adaptadores.falso import EjemplosFalsos
from adaptadores.fabrica import crear_proveedor
from app import create_app
from dominio.ejemplo import Ejemplo
from dominio.puertos import ProveedorEjemplos, ProveedorNoDisponible

URL = "/api/v2/ejemplos/{}/"


class ProveedorCaido(ProveedorEjemplos):
    nombre = "caido"

    def obtener(self, hanzi, idioma, limite):
        raise ProveedorNoDisponible("timeout")


class ProveedorEspia(ProveedorEjemplos):
    """Registra con qué argumentos lo llama el caso de uso y devuelve de más."""

    nombre = "espia"

    def __init__(self):
        self.llamadas = []

    def obtener(self, hanzi, idioma, limite):
        self.llamadas.append((hanzi, idioma, limite))
        return [Ejemplo(texto=f"{hanzi}{i}") for i in range(limite + 3)]


def cliente(proveedor=None):
    return create_app({"TESTING": True, "PROVEEDOR_EJEMPLOS": "falso"}, proveedor=proveedor).test_client()


def assert_error_json(resp, estado, codigo):
    assert resp.status_code == estado
    assert resp.is_json
    assert resp.get_json()["codigo"] == codigo


# --- Endpoint con el adaptador falso ---

def test_devuelve_ejemplos_en_espanol_por_defecto():
    resp = cliente().get(URL.format("学"))

    assert resp.status_code == 200
    datos = resp.get_json()
    assert datos["hanzi"] == "学"
    assert datos["idioma"] == "es"
    assert datos["proveedor"] == "falso"
    assert datos["ejemplos"][0] == {
        "texto": "我学中文。",
        "pinyin": "wǒ xué zhōngwén",
        "traduccion": "Estudio chino.",
    }


def test_traduce_al_ingles_con_lang_en():
    datos = cliente().get(URL.format("学") + "?lang=en").get_json()

    assert datos["idioma"] == "en"
    assert datos["ejemplos"][0]["traduccion"] == "I study Chinese."


def test_respeta_el_limite():
    datos = cliente().get(URL.format("学") + "?limite=2").get_json()

    assert len(datos["ejemplos"]) == 2


def test_caracter_sin_ejemplos_devuelve_lista_vacia():
    resp = cliente().get(URL.format("龍"))

    assert resp.status_code == 200
    assert resp.get_json()["ejemplos"] == []


# --- Validación de la entrada ---

@pytest.mark.parametrize("hanzi", ["abc", "学a", "学习学习学", "1"])
def test_rechaza_lo_que_no_son_caracteres_chinos(hanzi):
    assert_error_json(cliente().get(URL.format(hanzi)), 400, "ENTRADA_INVALIDA")


@pytest.mark.parametrize("consulta", ["?lang=fr", "?limite=0", "?limite=11", "?limite=dos"])
def test_rechaza_parametros_invalidos(consulta):
    assert_error_json(cliente().get(URL.format("学") + consulta), 400, "ENTRADA_INVALIDA")


def test_acepta_palabras_de_varios_caracteres():
    assert cliente().get(URL.format("学习")).status_code == 200


# --- Patrón Adapter: el caso de uso solo conoce el puerto ---

def test_proveedor_caido_responde_503_en_json():
    resp = cliente(ProveedorCaido()).get(URL.format("学"))

    assert_error_json(resp, 503, "PROVEEDOR_NO_DISPONIBLE")
    assert "timeout" not in resp.get_data(as_text=True)


def test_funciona_con_cualquier_implementacion_del_puerto():
    espia = ProveedorEspia()

    datos = cliente(espia).get(URL.format("人") + "?lang=en&limite=3").get_json()

    assert espia.llamadas == [("人", "en", 3)]
    assert datos["proveedor"] == "espia"
    # Aunque el proveedor devuelva de más, el caso de uso corta en el límite.
    assert len(datos["ejemplos"]) == 3


def test_fabrica_crea_el_adaptador_configurado():
    assert isinstance(crear_proveedor({"PROVEEDOR_EJEMPLOS": "falso"}), EjemplosFalsos)


def test_fabrica_rechaza_un_proveedor_desconocido():
    with pytest.raises(ValueError, match="no-existe"):
        create_app({"PROVEEDOR_EJEMPLOS": "no-existe"})
