"""Casos de uso y endpoints.

Port de SesionEstudioServiceTest, ResponderEjercicioServiceTest (la parte de
la sesión) y ResponderEjercicioViewTest de agente-tutor/tutor/tests.py.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from modelos import Ejercicio, SesionEstudio
from servicio import ResponderEjercicioService, SesionEstudioService
from tests.conftest import USUARIO, MotorFalso, ProgresoFalso


def contar(sesion_db, modelo):
    return sesion_db.scalar(select(func.count()).select_from(modelo))


# ---------- crear sesión (SesionEstudioServiceTest) ----------


def test_crea_sesion_con_refuerzos_primero(crear_sesion):
    datos = crear_sesion(nivel_hsk=2)

    assert datos["estado"] == "activa"
    assert len(datos["ejercicios"]) == 6
    assert [e["caracter"] for e in datos["ejercicios"][:2]] == ["目", "且"]
    assert all(e["es_refuerzo"] for e in datos["ejercicios"][:2])
    assert datos["ejercicios"][0]["tipo"] == "trazo"
    assert datos["dificultad"] == 3


def test_notifica_una_vez(crear_sesion, notificador):
    datos = crear_sesion()

    assert notificador.llamadas == [(USUARIO, datos["id"])]


def test_rechaza_nivel_bloqueado_con_el_mensaje_de_v1(client, sesion_db):
    resp = client.post("/api/v2/sesiones/", json={"usuario_id": str(USUARIO), "nivel_hsk": 5})

    assert resp.status_code == 400
    assert resp.get_json() == {
        "error": "HSK5 aún no está desbloqueado (máximo actual: HSK2).",
        "codigo": "NIVEL_NO_PERMITIDO",
    }
    assert contar(sesion_db, SesionEstudio) == 0


def test_sin_ejercicios_suficientes_no_guarda_nada(app, sesion_db):
    progreso = ProgresoFalso(refuerzos=())
    motor = MotorFalso()
    motor.seleccionar_caracteres_nuevos = lambda progreso, cantidad: ["学"]
    servicio = SesionEstudioService(motor, app.extensions["dependencias"].notificador, progreso)

    from dominio.excepciones import SesionInvalidaError

    with pytest.raises(SesionInvalidaError):
        servicio.crear_sesion_adaptativa(sesion_db, USUARIO, nivel_hsk=1)
    assert contar(sesion_db, SesionEstudio) == 0
    assert contar(sesion_db, Ejercicio) == 0


def test_duracion_por_defecto_y_personalizada(crear_sesion):
    assert crear_sesion()["duracion_estimada_min"] == 10
    assert crear_sesion(duracion_min=25)["duracion_estimada_min"] == 25


def test_acepta_usuario_id_entero_como_drf(client):
    resp = client.post("/api/v2/sesiones/", json={"usuario_id": 1, "nivel_hsk": 1})

    assert resp.status_code == 201
    assert resp.get_json()["usuario_id"] == "00000000-0000-0000-0000-000000000001"


@pytest.mark.parametrize("cuerpo", [
    {"nivel_hsk": 1},
    {"usuario_id": "no-es-uuid", "nivel_hsk": 1},
    {"usuario_id": True, "nivel_hsk": 1},
    {"usuario_id": 1},
    {"usuario_id": 1, "nivel_hsk": 0},
    {"usuario_id": 1, "nivel_hsk": 7},
    {"usuario_id": 1, "nivel_hsk": 1.5},
    {"usuario_id": 1, "nivel_hsk": 1, "duracion_min": 4},
    {"usuario_id": 1, "nivel_hsk": 1, "duracion_min": 61},
    [1, 2],
])
def test_crear_sesion_entrada_invalida(client, cuerpo):
    resp = client.post("/api/v2/sesiones/", json=cuerpo)

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"


def test_crear_sesion_sin_json(client):
    resp = client.post("/api/v2/sesiones/", data="hola", content_type="text/plain")

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"


# ---------- detalle ----------


def test_detalle_de_sesion(client, crear_sesion):
    creada = crear_sesion()

    resp = client.get(f"/api/v2/sesiones/{creada['id']}/")

    assert resp.status_code == 200
    assert resp.get_json() == creada
    assert creada["creada_en"].endswith("Z")


def test_detalle_inexistente_devuelve_404(client):
    resp = client.get("/api/v2/sesiones/9999/")

    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Sesión no encontrada.", "codigo": "NO_ENCONTRADO"}


# ---------- responder (ResponderEjercicioServiceTest y ViewTest) ----------


def responder(client, ejercicio_id, acerto=True):
    return client.post(f"/api/v2/ejercicios/{ejercicio_id}/responder/", json={"acerto": acerto})


def test_acertar_marca_el_ejercicio_y_agenda_repaso(client, crear_sesion, sesion_db, progreso):
    ejercicio = crear_sesion()["ejercicios"][0]

    resp = responder(client, ejercicio["id"], True)

    assert resp.status_code == 200
    datos = resp.get_json()
    assert datos["ejercicio"] == ejercicio
    assert datos["proximo_repaso"] is not None
    assert datos["tasa_acierto"] == 0.55
    guardado = sesion_db.get(Ejercicio, ejercicio["id"])
    assert guardado.respondido and guardado.fue_correcto
    assert guardado.respondido_en is not None
    assert progreso.respuestas == [(USUARIO, "目", True)]


def test_fallar_registra_el_error_en_progreso(client, crear_sesion, sesion_db, progreso):
    ejercicio = crear_sesion()["ejercicios"][0]

    datos = responder(client, ejercicio["id"], False).get_json()

    assert progreso.respuestas == [(USUARIO, "目", False)]
    assert datos["tasa_acierto"] == 0.45
    assert sesion_db.get(Ejercicio, ejercicio["id"]).fue_correcto is False


def test_proximo_repaso_crece_con_la_racha(app, crear_sesion, sesion_db, progreso):
    momento = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    servicio = ResponderEjercicioService(progreso, reloj=lambda: momento)
    progreso.rachas["目"] = 2  # Ya lo acertó dos veces seguidas.
    ejercicio = crear_sesion()["ejercicios"][0]

    resultado = servicio.responder(sesion_db, ejercicio["id"], True)

    # Tercer acierto seguido: 7 días, en ISO con +00:00 como la agenda de v1.
    assert resultado["proximo_repaso"] == (momento + timedelta(days=7)).isoformat()
    assert resultado["proximo_repaso"].endswith("+00:00")


def test_fallar_agenda_en_12_horas(app, crear_sesion, sesion_db, progreso):
    momento = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    servicio = ResponderEjercicioService(progreso, reloj=lambda: momento)
    ejercicio = crear_sesion()["ejercicios"][0]

    resultado = servicio.responder(sesion_db, ejercicio["id"], False)

    assert resultado["proximo_repaso"] == "2026-10-24T00:00:00+00:00"


def test_no_se_puede_responder_dos_veces(client, crear_sesion, progreso):
    ejercicio = crear_sesion()["ejercicios"][0]
    responder(client, ejercicio["id"])

    resp = responder(client, ejercicio["id"])

    assert resp.status_code == 409
    assert resp.get_json() == {
        "error": f"El ejercicio {ejercicio['id']} ya fue respondido.",
        "codigo": "EJERCICIO_YA_RESPONDIDO",
    }
    assert len(progreso.respuestas) == 1


def test_ejercicio_inexistente_devuelve_404(client):
    resp = responder(client, 9999)

    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Ejercicio no encontrado.", "codigo": "NO_ENCONTRADO"}


def test_la_sesion_se_cierra_al_responder_todo(client, crear_sesion, sesion_db):
    ejercicios = crear_sesion()["ejercicios"]

    for i, ejercicio in enumerate(ejercicios):
        datos = responder(client, ejercicio["id"]).get_json()
        assert datos["pendientes"] == len(ejercicios) - i - 1
        assert datos["sesion_completada"] == (i == len(ejercicios) - 1)

    sesion_id = sesion_db.get(Ejercicio, ejercicios[0]["id"]).sesion_id
    assert client.get(f"/api/v2/sesiones/{sesion_id}/").get_json()["estado"] == "completada"


@pytest.mark.parametrize("valor, esperado", [
    (True, True), (False, False), ("true", True), ("0", False), (1, True), ("no", False),
])
def test_acerto_acepta_los_valores_de_drf(client, crear_sesion, progreso, valor, esperado):
    ejercicio = crear_sesion()["ejercicios"][0]

    assert client.post(
        f"/api/v2/ejercicios/{ejercicio['id']}/responder/", json={"acerto": valor}
    ).status_code == 200
    assert progreso.respuestas[-1][2] is esperado


@pytest.mark.parametrize("cuerpo", [{}, {"acerto": "quizas"}, {"acerto": [1]}, {"acerto": None}, ["si"]])
def test_respuesta_invalida_devuelve_400_y_no_marca_nada(client, crear_sesion, sesion_db, cuerpo):
    ejercicio = crear_sesion()["ejercicios"][0]

    resp = client.post(f"/api/v2/ejercicios/{ejercicio['id']}/responder/", json=cuerpo)

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"
    assert sesion_db.get(Ejercicio, ejercicio["id"]).respondido is False


# ---------- progreso caído ----------


def test_progreso_caido_guarda_la_respuesta_y_devuelve_aviso(client, crear_sesion, sesion_db, progreso):
    ejercicio = crear_sesion()["ejercicios"][0]
    progreso.caido = True

    resp = responder(client, ejercicio["id"])

    assert resp.status_code == 200
    datos = resp.get_json()
    assert datos["proximo_repaso"] is None
    assert datos["tasa_acierto"] is None
    assert "no se pudo actualizar el progreso" in datos["aviso"]
    assert sesion_db.get(Ejercicio, ejercicio["id"]).respondido is True
    # Ya quedó respondido: no se puede volver a responder.
    assert responder(client, ejercicio["id"]).status_code == 409
