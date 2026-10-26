"""Contrato con v1 y con los servicios de los que depende.

- Los umbrales del significado son los de
  agente-tutor/tutor/domain/evaluacion_logic.py.
- Los campos del veredicto de trazo siguen el orden de
  ResultadoComparacionSerializer (contenido/caracteres/serializers.py),
  sin los dos que trazos-flask no devuelve.
- trazos-flask devuelve todos esos campos, y catalogo-flask manda
  `secuencia` y `mediana` en cada trazo.

Todo se lee con `ast`, sin importar Django ni el código de los otros
servicios. Si una carpeta no está (por ejemplo, dentro de la imagen
Docker), su prueba se salta.
"""

import ast
from pathlib import Path

import pytest

from dominio.evaluacion import UMBRALES_SIGNIFICADO
from serializacion import CAMPOS_TRAZO

SERVICIOS = Path(__file__).resolve().parents[2]
EVALUACION_V1 = SERVICIOS / "agente-tutor" / "tutor" / "domain" / "evaluacion_logic.py"
SERIALIZERS_CONTENIDO = SERVICIOS / "contenido" / "caracteres" / "serializers.py"
SERVICIO_TRAZOS = SERVICIOS / "trazos-flask" / "servicio.py"
SERIALIZACION_CATALOGO = SERVICIOS / "catalogo-flask" / "serializacion.py"

# trazos-flask no expone estos dos campos de v1.
SOLO_EN_V1 = {"distancia_media", "razon_longitud"}


def _arbol(ruta):
    if not ruta.exists():
        pytest.skip(f"{ruta.relative_to(SERVICIOS)} no está disponible")
    return ast.parse(ruta.read_text(encoding="utf-8"))


def _claves_de_dicts(nodo):
    """Claves de texto de cada dict literal dentro del nodo, en orden."""
    return [
        [k.value for k in d.keys if isinstance(k, ast.Constant)]
        for d in ast.walk(nodo)
        if isinstance(d, ast.Dict)
    ]


def test_umbrales_iguales_a_v1():
    for nodo in _arbol(EVALUACION_V1).body:
        if isinstance(nodo, ast.Assign) and nodo.targets[0].id == "UMBRALES_SIGNIFICADO":
            assert ast.literal_eval(nodo.value) == UMBRALES_SIGNIFICADO
            return
    pytest.fail("No se encontró UMBRALES_SIGNIFICADO en v1")


def test_campos_de_trazo_en_el_orden_de_v1():
    for clase in _arbol(SERIALIZERS_CONTENIDO).body:
        if isinstance(clase, ast.ClassDef) and clase.name == "ResultadoComparacionSerializer":
            campos_v1 = [
                n.targets[0].id for n in clase.body
                if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
            ]
            assert "aprobado" in campos_v1
            assert list(CAMPOS_TRAZO) == [c for c in campos_v1 if c not in SOLO_EN_V1]
            return
    pytest.fail("No se encontró ResultadoComparacionSerializer en contenido")


def test_trazos_flask_devuelve_todos_los_campos():
    for funcion in _arbol(SERVICIO_TRAZOS).body:
        if isinstance(funcion, ast.FunctionDef) and funcion.name == "validar_trazo":
            claves = _claves_de_dicts(funcion)
            assert any(set(CAMPOS_TRAZO) <= set(c) for c in claves), claves
            return
    pytest.fail("No se encontró validar_trazo en trazos-flask")


def test_catalogo_manda_secuencia_y_mediana_por_trazo():
    claves = _claves_de_dicts(_arbol(SERIALIZACION_CATALOGO))

    assert any({"secuencia", "mediana"} <= set(c) for c in claves), claves
