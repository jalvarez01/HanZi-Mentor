"""Contrato con v1: GET /api/v2/progreso/<id>/ tiene las mismas claves, en el
mismo orden, que ProgresoUsuarioSerializer de services/agente-tutor.

El frontend y flask_sesiones (T12) consumen esta forma. El serializer se lee
con `ast`, sin importar Django. Si la carpeta de agente-tutor no está (por
ejemplo, dentro de la imagen Docker), la prueba se salta.
"""

import ast
from pathlib import Path

import pytest

from tests.conftest import USUARIO

SERIALIZER = (
    Path(__file__).resolve().parents[2] / "agente-tutor" / "progreso" / "serializers.py"
)

pytestmark = pytest.mark.skipif(
    not SERIALIZER.exists(), reason="services/agente-tutor no está disponible"
)


@pytest.fixture(scope="module")
def campos_v1():
    for clase in ast.parse(SERIALIZER.read_text(encoding="utf-8")).body:
        if isinstance(clase, ast.ClassDef) and clase.name == "ProgresoUsuarioSerializer":
            for nodo in clase.body:
                if isinstance(nodo, ast.ClassDef) and nodo.name == "Meta":
                    for asignacion in nodo.body:
                        if isinstance(asignacion, ast.Assign) and asignacion.targets[0].id == "fields":
                            return ast.literal_eval(asignacion.value)
    pytest.fail("No se encontró ProgresoUsuarioSerializer.Meta.fields")


def test_contrato_usuario_nuevo(client, campos_v1):
    assert list(client.get(f"/api/v2/progreso/{USUARIO}/").get_json()) == campos_v1


def test_contrato_usuario_con_progreso(client, responder, campos_v1):
    responder("学", False)

    datos = client.get(f"/api/v2/progreso/{USUARIO}/").get_json()

    assert list(datos) == campos_v1
    assert list(datos["caracteres_debiles"][0]) == ["caracter", "fallos"]


def test_contrato_respuesta_devuelve_el_mismo_progreso(client, responder, campos_v1):
    datos = responder("学", True)

    assert list(datos) == campos_v1
    assert datos == client.get(f"/api/v2/progreso/{USUARIO}/").get_json()
