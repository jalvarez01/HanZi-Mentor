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


# ---------- codigo_error (RF-IA-01) ----------


def responder_con(client, ejercicio_id, **cuerpo):
    return client.post(f"/api/v2/ejercicios/{ejercicio_id}/responder/", json=cuerpo)


@pytest.mark.parametrize("codigo", ["PINYIN_INICIAL", "TRAZO_AUTOCALIFICADO", "NO_SABE", "TRAZO_INVERTIDO"])
def test_el_codigo_error_de_un_fallo_llega_a_progreso(client, crear_sesion, progreso, codigo):
    ejercicio = crear_sesion()["ejercicios"][0]
    sin_codigo = responder(client, crear_sesion()["ejercicios"][0]["id"], False).get_json()

    resp = responder_con(client, ejercicio["id"], acerto=False, codigo_error=codigo)

    assert resp.status_code == 200
    # La respuesta tiene la misma forma con o sin código.
    assert list(resp.get_json()) == list(sin_codigo)
    assert progreso.respuestas[-1] == (USUARIO, "目", False)
    assert progreso.codigos == [None, codigo]


def test_sin_codigo_error_o_con_null_no_se_manda_nada(client, crear_sesion, progreso):
    ejercicios = crear_sesion()["ejercicios"]

    assert responder_con(client, ejercicios[0]["id"], acerto=False).status_code == 200
    assert responder_con(client, ejercicios[1]["id"], acerto=False, codigo_error=None).status_code == 200

    assert progreso.codigos == [None, None]


@pytest.mark.parametrize("codigo", ["OTRO_CODIGO", "", "no_sabe", 7, True, ["NO_SABE"], {"a": 1}])
def test_codigo_error_invalido_devuelve_400_y_no_marca_nada(client, crear_sesion, sesion_db, progreso, codigo):
    ejercicio = crear_sesion()["ejercicios"][0]

    resp = responder_con(client, ejercicio["id"], acerto=False, codigo_error=codigo)

    assert resp.status_code == 400
    assert resp.get_json() == {
        "error": "El campo 'codigo_error' no es un código de error conocido",
        "codigo": "ENTRADA_INVALIDA",
    }
    assert sesion_db.get(Ejercicio, ejercicio["id"]).respondido is False
    assert progreso.respuestas == []


@pytest.mark.parametrize("codigo", ["PINYIN_INICIAL", "OTRO_CODIGO", 7])
def test_codigo_error_con_acierto_se_ignora(client, crear_sesion, sesion_db, progreso, codigo):
    ejercicio = crear_sesion()["ejercicios"][0]

    resp = responder_con(client, ejercicio["id"], acerto=True, codigo_error=codigo)

    assert resp.status_code == 200
    assert sesion_db.get(Ejercicio, ejercicio["id"]).fue_correcto is True
    assert progreso.codigos == [None]


def test_el_servicio_no_manda_codigo_con_un_acierto(crear_sesion, sesion_db, progreso):
    ejercicio = crear_sesion()["ejercicios"][0]

    ResponderEjercicioService(progreso).responder(
        sesion_db, ejercicio["id"], True, codigo_error="NO_SABE"
    )

    assert progreso.codigos == [None]


def test_progreso_caido_con_codigo_error_guarda_la_respuesta(client, crear_sesion, sesion_db, progreso):
    ejercicio = crear_sesion()["ejercicios"][0]
    progreso.caido = True

    resp = responder_con(client, ejercicio["id"], acerto=False, codigo_error="NO_SABE")

    assert resp.status_code == 200
    assert "aviso" in resp.get_json()
    assert sesion_db.get(Ejercicio, ejercicio["id"]).respondido is True



# ---------- RF-IA-02: composición de la sesión ----------


def crear_con(app, sesion_db, progreso, nuevos=("学", "校", "老", "师", "大", "小", "中", "山")):
    motor = MotorFalso()
    motor.seleccionar_caracteres_nuevos = lambda prog, cantidad: list(nuevos)[:cantidad]
    servicio = SesionEstudioService(motor, app.extensions["dependencias"].notificador, progreso)
    sesion = servicio.crear_sesion_adaptativa(sesion_db, USUARIO, nivel_hsk=1)
    return [(e.caracter, e.tipo, e.es_refuerzo) for e in sesion.ejercicios]


def test_vencidos_primero_luego_refuerzos_y_nuevos_hasta_7(app, sesion_db):
    progreso = ProgresoFalso(vencidos=("人", "大"), refuerzos=("目",))

    ejercicios = crear_con(app, sesion_db, progreso)

    assert ejercicios == [
        ("人", "significado", True),
        ("大", "significado", True),
        ("目", "trazo", True),
        ("学", "significado", False),
        ("校", "significado", False),
        ("老", "significado", False),
        ("师", "significado", False),
    ]


def test_con_4_vencidos_y_3_refuerzos_va_1_nuevo_y_son_8(app, sesion_db):
    progreso = ProgresoFalso(vencidos=("一", "二", "三", "四", "五"), refuerzos=("目", "且", "月"))

    ejercicios = crear_con(app, sesion_db, progreso)

    assert len(ejercicios) == 8
    assert [c for c, _, _ in ejercicios] == ["一", "二", "三", "四", "目", "且", "月", "学"]


def test_sin_vencidos_ni_refuerzos_son_7_nuevos(app, sesion_db):
    ejercicios = crear_con(app, sesion_db, ProgresoFalso(refuerzos=()))

    assert [c for c, _, _ in ejercicios] == ["学", "校", "老", "师", "大", "小", "中"]
    assert not any(es_refuerzo for _, _, es_refuerzo in ejercicios)


def test_ningun_caracter_se_repite_en_ninguna_combinacion(app, sesion_db):
    # 人 es vencido y refuerzo; 目 es refuerzo y nuevo; 人 también es nuevo.
    progreso = ProgresoFalso(vencidos=("人",), refuerzos=("人", "目", "且", "月"))

    ejercicios = crear_con(app, sesion_db, progreso, nuevos=("目", "人", "学", "校", "老", "师"))

    caracteres = [c for c, _, _ in ejercicios]
    assert caracteres == ["人", "目", "且", "月", "学", "校", "老"]
    assert len(set(caracteres)) == len(caracteres)
    # Se pide un refuerzo de más por cada vencido: aunque 人 ya salió como
    # vencido, los refuerzos se completan a 3.
    assert [c for c, tipo, _ in ejercicios if tipo == "trazo"] == ["目", "且", "月"]


def test_el_duplicado_anterior_entre_refuerzos_y_nuevos_ya_no_ocurre(app, sesion_db):
    progreso = ProgresoFalso(refuerzos=("学", "目"))

    ejercicios = crear_con(app, sesion_db, progreso, nuevos=("学", "校", "老", "师", "大", "小"))

    assert [c for c, _, _ in ejercicios] == ["学", "目", "校", "老", "师", "大", "小"]


def test_si_repasos_falla_la_sesion_se_crea_sin_vencidos(app, sesion_db):
    progreso = ProgresoFalso(vencidos=("人", "大"), refuerzos=("目",))
    progreso.repasos_vencidos = lambda usuario_id, limite=4: []   # como ProgresoRemoto caído

    ejercicios = crear_con(app, sesion_db, progreso)

    assert ejercicios[0] == ("目", "trazo", True)
    assert len(ejercicios) == 7


def test_la_respuesta_de_crear_no_cambia_de_forma_con_vencidos(client, progreso):
    progreso.vencidos = ["人"]

    datos = client.post("/api/v2/sesiones/", json={"usuario_id": str(USUARIO), "nivel_hsk": 2}).get_json()

    # Las claves de v1 y, al final, `patron` (RF-IA-03).
    assert list(datos["ejercicios"][0]) == ["id", "caracter", "tipo", "dificultad", "es_refuerzo", "patron"]
    assert datos["ejercicios"][0]["caracter"] == "人"


# ---------- RF-IA-02: codigo_error guardado y curva al cerrar ----------


def responder_todo(client, ejercicios, cuerpos):
    """Responde cada ejercicio con su cuerpo (por defecto, acierto)."""
    ultimo = None
    for i, ejercicio in enumerate(ejercicios):
        cuerpo = cuerpos.get(i, {"acerto": True})
        ultimo = client.post(f"/api/v2/ejercicios/{ejercicio['id']}/responder/", json=cuerpo)
    return ultimo


def test_codigo_error_se_guarda_en_el_ejercicio_y_null_con_acierto(client, crear_sesion, sesion_db):
    ejercicios = crear_sesion()["ejercicios"]

    client.post(f"/api/v2/ejercicios/{ejercicios[0]['id']}/responder/",
                json={"acerto": False, "codigo_error": "NO_SABE"})
    client.post(f"/api/v2/ejercicios/{ejercicios[1]['id']}/responder/",
                json={"acerto": True, "codigo_error": "NO_SABE"})
    client.post(f"/api/v2/ejercicios/{ejercicios[2]['id']}/responder/", json={"acerto": False})

    assert [sesion_db.get(Ejercicio, e["id"]).codigo_error for e in ejercicios[:3]] == [
        "NO_SABE", None, None,
    ]


def test_al_cerrar_se_pide_la_curva_una_vez_con_todas_las_respuestas(client, crear_sesion, progreso):
    creada = crear_sesion()
    ejercicios = creada["ejercicios"]

    ultima = responder_todo(client, ejercicios, {
        0: {"acerto": False, "codigo_error": "NO_SABE"},
        1: {"acerto": False, "codigo_error": "PINYIN_FINAL"},
        2: {"acerto": False},
    })

    assert ultima.get_json()["sesion_completada"] is True
    assert len(progreso.curvas) == 1
    usuario_id, sesion_id, cerrada_en, respuestas = progreso.curvas[0]
    assert (usuario_id, sesion_id) == (USUARIO, creada["id"])
    assert respuestas == [
        {"caracter": ejercicios[0]["caracter"], "acerto": False, "codigo_error": "NO_SABE"},
        {"caracter": ejercicios[1]["caracter"], "acerto": False, "codigo_error": "PINYIN_FINAL"},
        {"caracter": ejercicios[2]["caracter"], "acerto": False},
    ] + [{"caracter": e["caracter"], "acerto": True} for e in ejercicios[3:]]
    assert datetime.fromisoformat(cerrada_en).tzinfo is not None


def test_cerrada_en_es_la_fecha_de_la_ultima_respuesta(app, crear_sesion, sesion_db, progreso):
    ejercicios = crear_sesion()["ejercicios"]
    inicio = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    for i, ejercicio in enumerate(ejercicios):
        ResponderEjercicioService(progreso, reloj=lambda i=i: inicio + timedelta(minutes=i)).responder(
            sesion_db, ejercicio["id"], True
        )

    cerrada_en = progreso.curvas[0][2]
    assert cerrada_en == (inicio + timedelta(minutes=len(ejercicios) - 1)).isoformat()
    assert cerrada_en.endswith("+00:00")


def test_antes_de_cerrar_no_se_pide_la_curva(client, crear_sesion, progreso):
    ejercicios = crear_sesion()["ejercicios"]

    responder_todo(client, ejercicios[:-1], {})

    assert progreso.curvas == []


def test_la_curva_va_despues_de_registrar_la_ultima_respuesta(client, crear_sesion, progreso):
    orden = []
    registrar, curva = progreso.registrar_respuesta, progreso.aplicar_curva_olvido
    progreso.registrar_respuesta = lambda *a, **k: (orden.append("respuesta"), registrar(*a, **k))[1]
    progreso.aplicar_curva_olvido = lambda *a, **k: (orden.append("curva"), curva(*a, **k))[1]

    responder_todo(client, crear_sesion()["ejercicios"], {})

    assert orden[-2:] == ["respuesta", "curva"]


def test_la_respuesta_que_cierra_solo_suma_el_desempeno(client, crear_sesion, progreso):
    ejercicios = crear_sesion()["ejercicios"]
    anterior = client.post(f"/api/v2/ejercicios/{ejercicios[0]['id']}/responder/", json={"acerto": True}).get_json()

    ultima = responder_todo(client, ejercicios[1:], {}).get_json()

    assert list(ultima) == list(anterior) + ["desempeno"]
    assert ultima["proximo_repaso"] is not None


def test_si_la_curva_falla_responder_da_200_y_la_sesion_queda_completada(client, crear_sesion, progreso):
    creada = crear_sesion()
    progreso.aplicar_curva_olvido = lambda *a, **k: None   # progreso no aplicó la curva

    ultima = responder_todo(client, creada["ejercicios"], {})

    assert ultima.status_code == 200
    assert ultima.get_json()["sesion_completada"] is True
    assert "aviso" not in ultima.get_json()
    assert client.get(f"/api/v2/sesiones/{creada['id']}/").get_json()["estado"] == "completada"


def test_con_progreso_caido_al_cerrar_responder_da_200_con_el_aviso(client, crear_sesion, progreso):
    creada = crear_sesion()
    ejercicios = creada["ejercicios"]
    responder_todo(client, ejercicios[:-1], {})
    progreso.caido = True

    ultima = client.post(f"/api/v2/ejercicios/{ejercicios[-1]['id']}/responder/", json={"acerto": True})

    assert ultima.status_code == 200
    assert ultima.get_json()["sesion_completada"] is True
    assert "no se pudo actualizar el progreso" in ultima.get_json()["aviso"]
    assert client.get(f"/api/v2/sesiones/{creada['id']}/").get_json()["estado"] == "completada"
    # Se intentó una vez y no se reintenta.
    assert len(progreso.curvas) == 1
