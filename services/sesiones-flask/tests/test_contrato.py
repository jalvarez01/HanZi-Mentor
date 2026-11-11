"""Contrato con v1: las respuestas tienen las mismas claves, en el mismo orden,
que los serializers de agente-tutor/tutor/serializers.py.

El frontend consume esta forma. Los serializers se leen con `ast`, sin
importar Django. Si la carpeta de agente-tutor no está (por ejemplo, dentro
de la imagen Docker), la prueba se salta.
"""

import ast
from pathlib import Path

import pytest

SERIALIZERS = (
    Path(__file__).resolve().parents[2] / "agente-tutor" / "tutor" / "serializers.py"
)

pytestmark = pytest.mark.skipif(
    not SERIALIZERS.exists(), reason="services/agente-tutor no está disponible"
)


def _campos_declarados(clase):
    """Campos declarados como atributos (Serializer sin Meta), en orden."""
    return [
        nodo.targets[0].id
        for nodo in clase.body
        if isinstance(nodo, ast.Assign)
        and isinstance(nodo.value, ast.Call)
        and isinstance(nodo.value.func, ast.Attribute | ast.Name)
    ]


@pytest.fixture(scope="module")
def v1():
    resultado = {}
    for clase in ast.parse(SERIALIZERS.read_text(encoding="utf-8")).body:
        if not isinstance(clase, ast.ClassDef):
            continue
        campos = _campos_declarados(clase)
        for nodo in clase.body:
            if isinstance(nodo, ast.ClassDef) and nodo.name == "Meta":
                for asignacion in nodo.body:
                    if isinstance(asignacion, ast.Assign) and asignacion.targets[0].id == "fields":
                        campos = ast.literal_eval(asignacion.value)
        resultado[clase.name] = campos
    return resultado


def test_se_leyeron_los_serializers(v1):
    assert v1["EjercicioSerializer"] == ["id", "caracter", "tipo", "dificultad", "es_refuerzo"]
    assert "ejercicios" in v1["SesionEstudioSerializer"]
    assert v1["ResultadoRespuestaSerializer"][0] == "ejercicio"


# Claves que solo tiene v2 en cada ejercicio. Van al final, después de todas
# las de v1, para que un cliente de v1 no note la diferencia: `patron` es el
# patrón de error que originó un ejercicio adaptado (RF-IA-03), o null.
SOLO_V2_EJERCICIO = ["patron"]


def test_contrato_crear_y_detalle_de_sesion(client, crear_sesion, v1):
    creada = crear_sesion()
    detalle = client.get(f"/api/v2/sesiones/{creada['id']}/").get_json()

    for datos in (creada, detalle):
        assert list(datos) == v1["SesionEstudioSerializer"]
        for ejercicio in datos["ejercicios"]:
            assert list(ejercicio) == v1["EjercicioSerializer"] + SOLO_V2_EJERCICIO


def test_contrato_responder(client, crear_sesion, v1):
    ejercicio = crear_sesion()["ejercicios"][0]

    datos = client.post(
        f"/api/v2/ejercicios/{ejercicio['id']}/responder/", json={"acerto": True}
    ).get_json()

    assert list(datos) == v1["ResultadoRespuestaSerializer"]
    assert list(datos["ejercicio"]) == v1["EjercicioSerializer"] + SOLO_V2_EJERCICIO


def test_contrato_responder_degradado_solo_agrega_aviso(client, crear_sesion, progreso, v1):
    ejercicio = crear_sesion()["ejercicios"][0]
    progreso.caido = True

    datos = client.post(
        f"/api/v2/ejercicios/{ejercicio['id']}/responder/", json={"acerto": True}
    ).get_json()

    assert list(datos) == v1["ResultadoRespuestaSerializer"] + ["aviso"]


def test_contrato_la_respuesta_que_cierra_solo_agrega_desempeno(client, crear_sesion, v1):
    """RF-IA-05: las claves de v1 en su orden y `desempeno` al final."""
    ejercicios = crear_sesion()["ejercicios"]
    for ejercicio in ejercicios:
        datos = client.post(
            f"/api/v2/ejercicios/{ejercicio['id']}/responder/", json={"acerto": True}
        ).get_json()

    assert list(datos) == v1["ResultadoRespuestaSerializer"] + ["desempeno"]
    assert list(datos["ejercicio"]) == v1["EjercicioSerializer"] + SOLO_V2_EJERCICIO
