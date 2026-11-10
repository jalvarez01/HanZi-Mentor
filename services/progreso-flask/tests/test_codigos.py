"""La lista de códigos de error es la de evaluacion-flask más los dos de Práctica.

Los códigos de evaluación se leen de adaptadores/reglas.py con `ast`, sin
importar el otro servicio. Si su carpeta no está (por ejemplo, dentro de la
imagen Docker), la prueba se salta.
"""

import ast
from pathlib import Path

import pytest

from dominio import codigos

REGLAS = (
    Path(__file__).resolve().parents[2] / "evaluacion-flask" / "adaptadores" / "reglas.py"
)


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


@pytest.mark.skipif(not REGLAS.exists(), reason="services/evaluacion-flask no está disponible")
def test_los_codigos_de_evaluacion_son_los_de_evaluacion_flask():
    assert set(codigos.CODIGOS_EVALUACION) == codigos_de_evaluacion()


def test_la_lista_completa_y_la_de_trazos():
    assert len(codigos.CODIGOS_EVALUACION) == 12
    assert codigos.CODIGOS_ERROR == set(codigos.CODIGOS_EVALUACION) | {"TRAZO_AUTOCALIFICADO", "NO_SABE"}
    assert codigos.CODIGOS_TRAZO_EVALUADO == {
        c for c in codigos.CODIGOS_EVALUACION if c.startswith("TRAZO_")
    }
    assert "TRAZO_AUTOCALIFICADO" not in codigos.CODIGOS_TRAZO_EVALUADO
