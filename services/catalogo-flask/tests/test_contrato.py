"""Contrato con v1: cada respuesta de v2 tiene las mismas claves, en el mismo
orden, que los serializers de DRF en services/contenido.

agente-tutor (tutor/infra/catalogo.py) consume esta forma, así que v2 debe
poder reemplazar a v1 sin cambios en el cliente. Los serializers se leen con
`ast`, sin importar Django. Si la carpeta services/contenido no está (por
ejemplo, dentro de la imagen Docker), la prueba se salta.
"""

import ast
import uuid
from pathlib import Path

import pytest

CONTENIDO = Path(__file__).resolve().parents[2] / "contenido"
SERIALIZERS = [
    CONTENIDO / "caracteres" / "serializers.py",
    CONTENIDO / "lecciones" / "serializers.py",
]

pytestmark = pytest.mark.skipif(
    not all(ruta.exists() for ruta in SERIALIZERS),
    reason="services/contenido no está disponible",
)


def _leer_serializers():
    """{nombre: {"campos": [...], "anidados": {campo: serializer}}}"""
    resultado = {}
    for ruta in SERIALIZERS:
        for clase in ast.parse(ruta.read_text(encoding="utf-8")).body:
            if not isinstance(clase, ast.ClassDef):
                continue
            campos, anidados = None, {}
            for nodo in clase.body:
                if isinstance(nodo, ast.ClassDef) and nodo.name == "Meta":
                    for asignacion in nodo.body:
                        if isinstance(asignacion, ast.Assign) and asignacion.targets[0].id == "fields":
                            campos = ast.literal_eval(asignacion.value)
                elif (
                    isinstance(nodo, ast.Assign)
                    and isinstance(nodo.value, ast.Call)
                    and isinstance(nodo.value.func, ast.Name)
                    and nodo.value.func.id.endswith("Serializer")
                ):
                    anidados[nodo.targets[0].id] = nodo.value.func.id
            if campos is not None:
                resultado[clase.name] = {"campos": campos, "anidados": anidados}
    return resultado


@pytest.fixture(scope="module")
def v1():
    return _leer_serializers()


def comparar(datos, serializer, v1):
    """Compara claves y orden, y baja a los serializers anidados."""
    esperado = v1[serializer]
    assert list(datos) == esperado["campos"], f"{serializer}: claves distintas a v1"
    for campo, anidado in esperado["anidados"].items():
        valor = datos[campo]
        for item in valor if isinstance(valor, list) else [valor]:
            comparar(item, anidado, v1)


def test_se_leyeron_los_serializers_de_v1(v1):
    for nombre in ("TrazoSerializer", "CaracterSerializer", "CaracterListaSerializer",
                   "EjercicioSerializer", "LeccionSerializer"):
        assert nombre in v1


def test_contrato_lista_de_caracteres(client, crear_caracter, v1):
    crear_caracter("人")

    datos = client.get("/api/v2/caracteres/").get_json()

    assert list(datos) == ["caracteres"]
    comparar(datos["caracteres"][0], "CaracterListaSerializer", v1)


def test_contrato_detalle_de_caracter(client, crear_caracter, v1):
    crear_caracter("人", trazos=2)

    datos = client.get("/api/v2/caracteres/人/").get_json()

    assert len(datos["trazos"]) == 2
    comparar(datos, "CaracterSerializer", v1)


def test_contrato_generar_leccion(client, crear_caracter, v1):
    crear_caracter("人")

    datos = client.post(
        "/api/v2/lecciones/generar/", json={"usuario_id": str(uuid.uuid4()), "nivel_hsk": 1}
    ).get_json()

    assert len(datos["ejercicios"]) == 1
    comparar(datos, "LeccionSerializer", v1)


def test_contrato_detalle_de_leccion(client, crear_caracter, v1):
    crear_caracter("人")
    creada = client.post(
        "/api/v2/lecciones/generar/", json={"usuario_id": 1, "nivel_hsk": 1}
    ).get_json()

    datos = client.get(f"/api/v2/lecciones/{creada['id']}/").get_json()

    assert datos == creada
    comparar(datos, "LeccionSerializer", v1)
