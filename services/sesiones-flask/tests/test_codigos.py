"""La lista de códigos de error coincide con evaluacion-flask y con progreso-flask.

Los otros servicios se leen con `ast`, sin importarlos. Si sus carpetas no
están (por ejemplo, dentro de la imagen Docker), las pruebas se saltan.
"""

import ast
from pathlib import Path

import pytest

from dominio import codigos_error

SERVICIOS = Path(__file__).resolve().parents[2]
REGLAS = SERVICIOS / "evaluacion-flask" / "adaptadores" / "reglas.py"
PROGRESO = SERVICIOS / "progreso-flask" / "dominio" / "codigos.py"


def codigos_de_evaluacion():
    """El primer argumento de cada Explicacion("CODIGO", ...) de reglas.py."""
    encontrados = set()
    for nodo in ast.walk(ast.parse(REGLAS.read_text(encoding="utf-8"))):
        if not (isinstance(nodo, ast.Call) and getattr(nodo.func, "id", None) == "Explicacion"):
            continue
        primero = nodo.args[0]
        if isinstance(primero, ast.Constant):
            encontrados.add(primero.value)
        elif isinstance(primero, ast.Name) and primero.id == "codigo":
            # Explicacion(codigo, ...): los dos códigos de pinyin cercano.
            encontrados |= {"PINYIN_INICIAL", "PINYIN_FINAL"}
    return encontrados


def codigos_de_progreso():
    """Los textos en mayúsculas de dominio/codigos.py, salvo los orígenes."""
    return {
        nodo.value
        for nodo in ast.walk(ast.parse(PROGRESO.read_text(encoding="utf-8")))
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
        and nodo.value.isupper() and "\n" not in nodo.value
    }


@pytest.mark.skipif(not REGLAS.exists(), reason="services/evaluacion-flask no está disponible")
def test_los_codigos_de_evaluacion_son_los_de_evaluacion_flask():
    assert set(codigos_error.CODIGOS_EVALUACION) == codigos_de_evaluacion()


@pytest.mark.skipif(not PROGRESO.exists(), reason="services/progreso-flask no está disponible")
def test_la_lista_es_la_misma_que_la_de_progreso_flask():
    assert codigos_error.CODIGOS_ERROR == codigos_de_progreso()


def test_la_lista_completa():
    assert len(codigos_error.CODIGOS_ERROR) == 14
    assert {"TRAZO_AUTOCALIFICADO", "NO_SABE"} <= codigos_error.CODIGOS_ERROR
