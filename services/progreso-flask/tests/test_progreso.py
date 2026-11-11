"""Endpoints de progreso.

Las dos primeras son el port de agente-tutor/progreso/tests.py y las de
respuestas cubren lo que probaba ResponderEjercicioServiceTest sobre el
progreso (agente-tutor/tutor/tests.py).
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

import servicio
from modelos import ProgresoUsuario
from tests.conftest import USUARIO

URL = f"/api/v2/progreso/{USUARIO}/"


def contar(sesion):
    return sesion.scalar(select(func.count()).select_from(ProgresoUsuario))


def fecha(texto):
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def entidad(sesion):
    return sesion.scalars(select(ProgresoUsuario)).one()


# ---------- GET /progreso/<usuario_id>/ ----------


def test_devuelve_valores_iniciales_sin_persistir_progreso(client, sesion):
    resp = client.get(URL)

    assert resp.status_code == 200
    datos = resp.get_json()
    assert datos["usuario_id"] == USUARIO
    assert datos["nivel_hsk"] == 1
    assert datos["nivel_max_desbloqueado"] == 1
    assert datos["tasa_acierto"] == 0.5
    assert datos["caracteres_dominados"] == []
    assert datos["errores_frecuentes"] == {}
    assert datos["aciertos_consecutivos"] == {}
    assert datos["proximo_repaso"] is None
    assert datos["actualizado_en"] is None
    assert datos["total_dominados"] == 0
    assert datos["total_por_reforzar"] == 0
    assert datos["caracteres_debiles"] == []
    assert contar(sesion) == 0


def test_devuelve_el_resumen_completo_del_progreso_existente(client, sesion):
    sesion.add(ProgresoUsuario(
        usuario_id=uuid.UUID(USUARIO),
        nivel_hsk=2,
        nivel_max_desbloqueado=3,
        tasa_acierto=0.75,
        caracteres_dominados=["学", "校"],
        errores_frecuentes={"目": 2, "人": 5, "且": 3},
        aciertos_consecutivos={"学": 4},
    ))
    sesion.commit()

    datos = client.get(URL).get_json()

    assert datos["nivel_hsk"] == 2
    assert datos["nivel_max_desbloqueado"] == 3
    assert datos["total_dominados"] == 2
    assert datos["total_por_reforzar"] == 3
    assert datos["caracteres_debiles"] == [
        {"caracter": "人", "fallos": 5},
        {"caracter": "且", "fallos": 3},
        {"caracter": "目", "fallos": 2},
    ]
    assert datos["actualizado_en"].endswith("Z")


def test_caracteres_debiles_son_como_maximo_cinco(client, responder):
    for caracter in "一二三四五六七":
        responder(caracter, False)

    assert len(client.get(URL).get_json()["caracteres_debiles"]) == 5


def test_acepta_uuid_en_mayusculas_y_responde_normalizado(client):
    resp = client.get(f"/api/v2/progreso/{USUARIO.upper()}/")

    assert resp.status_code == 200
    assert resp.get_json()["usuario_id"] == USUARIO


@pytest.mark.parametrize("usuario", [
    "abc", "12345678123456781234567812345678", "12345678-1234-5678-1234-56781234567z",
])
def test_uuid_invalido_devuelve_400(client, usuario):
    for resp in (
        client.get(f"/api/v2/progreso/{usuario}/"),
        client.get(f"/api/v2/progreso/{usuario}/refuerzos/"),
        client.post(f"/api/v2/progreso/{usuario}/respuestas/", json={"caracter": "学", "acerto": True}),
    ):
        assert resp.status_code == 400
        assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"


# ---------- POST /progreso/<usuario_id>/respuestas/ ----------


def test_acertar_crea_el_progreso_sin_agendar_repaso(responder, sesion):
    """RF-IA-02: responder ya no agenda. El repaso se agenda al cerrar la
    sesión (POST .../curva-olvido/)."""
    datos = responder("学", True)

    assert contar(sesion) == 1
    assert datos["proximo_repaso"] is None
    assert datos["aciertos_consecutivos"] == {"学": 1}
    assert datos["actualizado_en"] is not None
    assert entidad(sesion).agenda_repaso == {}


def test_fallar_suma_a_errores_frecuentes(responder):
    datos = responder("学", False)

    assert datos["errores_frecuentes"] == {"学": 1}
    assert datos["aciertos_consecutivos"] == {"学": 0}
    assert datos["tasa_acierto"] == 0.45


def test_acertar_corta_los_errores_y_suma_racha(responder):
    datos = responder("学", True)

    assert datos["aciertos_consecutivos"] == {"学": 1}
    assert "学" in datos["caracteres_dominados"]
    assert datos["tasa_acierto"] == 0.55


def test_secuencia_domina_pierde_y_recupera(responder):
    """Un carácter entra a dominados, sale al fallar y vuelve tras pagar los fallos."""
    assert responder("学", True)["caracteres_dominados"] == ["学"]

    tras_fallo = responder("学", False)
    assert tras_fallo["caracteres_dominados"] == []
    assert tras_fallo["errores_frecuentes"] == {"学": 1}

    recuperado = responder("学", True)
    assert recuperado["caracteres_dominados"] == ["学"]
    assert recuperado["errores_frecuentes"] == {}
    assert recuperado["total_dominados"] == 1


def test_dos_fallos_necesitan_dos_aciertos(responder):
    responder("学", False)
    responder("学", False)

    assert responder("学", True)["caracteres_dominados"] == []
    assert responder("学", True)["caracteres_dominados"] == ["学"]


def test_la_agenda_guarda_una_fecha_por_caracter(sesion):
    """RF-IA-02: la agenda la escribe la curva al cerrar la sesión, no cada
    respuesta. Mismas fechas que antes para un acierto (1 día) y un fallo
    (12 horas) de un carácter nuevo."""
    momento = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    usuario = uuid.UUID(USUARIO)

    servicio.registrar_respuesta(sesion, usuario, "学", True, momento=momento)
    servicio.registrar_respuesta(sesion, usuario, "校", False, momento=momento)
    assert entidad(sesion).agenda_repaso == {}

    servicio.aplicar_curva_olvido(sesion, usuario, 1, momento, [
        {"caracter": "学", "acerto": True, "codigo_error": None},
        {"caracter": "校", "acerto": False, "codigo_error": None},
    ])

    progreso = entidad(sesion)
    assert progreso.agenda_repaso == {
        "学": "2026-10-24T12:00:00+00:00",
        "校": "2026-10-24T00:00:00+00:00",
    }
    # El más cercano de la agenda.
    assert progreso.proximo_repaso == momento + timedelta(hours=12)


def test_el_intervalo_crece_con_la_racha(sesion):
    """RF-IA-02: tres sesiones seguidas acertando 学. Con SM-2 los intervalos
    son 1, 6 y round(6 x 2.5) = 15 días (antes, 1, 3 y 7)."""
    momento = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    usuario = uuid.UUID(USUARIO)
    acierto = [{"caracter": "学", "acerto": True, "codigo_error": None}]

    agenda = []
    for sesion_id in (1, 2, 3):
        servicio.registrar_respuesta(sesion, usuario, "学", True, momento=momento)
        servicio.aplicar_curva_olvido(sesion, usuario, sesion_id, momento, acierto)
        agenda.append(entidad(sesion).agenda_repaso["学"])

    assert agenda == [
        "2026-10-24T12:00:00+00:00",
        "2026-10-29T12:00:00+00:00",
        "2026-11-07T12:00:00+00:00",
    ]


def test_respuestas_de_usuarios_distintos_no_se_mezclan(client, responder):
    otro = str(uuid.uuid4())
    responder("学", False)
    responder("人", True, usuario=otro)

    assert client.get(URL).get_json()["errores_frecuentes"] == {"学": 1}
    assert client.get(f"/api/v2/progreso/{otro}/").get_json()["caracteres_dominados"] == ["人"]


@pytest.mark.parametrize("cuerpo", [
    {"acerto": True},
    {"caracter": "", "acerto": True},
    {"caracter": "   ", "acerto": True},
    {"caracter": 5, "acerto": True},
    {"caracter": "学学学学学学学学学", "acerto": True},
    {"caracter": "学"},
    {"caracter": "学", "acerto": "si"},
    {"caracter": "学", "acerto": 1},
    ["学", True],
])
def test_respuesta_invalida_devuelve_400(client, cuerpo):
    resp = client.post(f"{URL}respuestas/", json=cuerpo)

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"


def test_respuesta_sin_json_devuelve_400(client, sesion):
    resp = client.post(f"{URL}respuestas/", data="no es json", content_type="text/plain")

    assert resp.status_code == 400
    assert contar(sesion) == 0


def test_respuestas_solo_acepta_post(client):
    resp = client.get(f"{URL}respuestas/")

    assert resp.status_code == 405
    assert resp.get_json()["codigo"] == "METODO_NO_PERMITIDO"


# ---------- GET /progreso/<usuario_id>/refuerzos/ ----------


def test_refuerzos_de_peor_a_mejor(client, responder):
    for caracter, fallos in [("目", 2), ("人", 5), ("且", 3)]:
        for _ in range(fallos):
            responder(caracter, False)

    datos = client.get(f"{URL}refuerzos/").get_json()

    assert datos == {"usuario_id": USUARIO, "caracteres": ["人", "且", "目"]}
    assert client.get(f"{URL}refuerzos/?limite=1").get_json()["caracteres"] == ["人"]


def test_refuerzos_de_usuario_nuevo_es_vacio(client):
    resp = client.get(f"{URL}refuerzos/")

    assert resp.status_code == 200
    assert resp.get_json()["caracteres"] == []


@pytest.mark.parametrize("limite", ["abc", "0", "-1", "51", "2.5", ""])
def test_limite_invalido_devuelve_400(client, limite):
    resp = client.get(f"{URL}refuerzos/", query_string={"limite": limite})

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"


# ---------- modelo ----------


def test_los_metodos_del_modelo_no_guardan(sesion):
    progreso = ProgresoUsuario(usuario_id=uuid.UUID(USUARIO))

    progreso.registrar_error("学")
    progreso.registrar_acierto("人")

    assert progreso.errores_frecuentes == {"学": 1}
    assert progreso.caracteres_dominados == ["人"]
    assert contar(sesion) == 0


# ---------- codigo_error en respuestas/ (RF-IA-01) ----------


def test_fallo_con_codigo_error_queda_en_el_historial(responder, sesion):
    responder("学", False, codigo_error="PINYIN_INICIAL")

    progreso = entidad(sesion)
    assert progreso.errores_por_codigo == {"PINYIN_INICIAL": 1}
    (fallo,) = progreso.historial_errores
    assert (fallo["codigo"], fallo["caracter"], fallo["origen"]) == ("PINYIN_INICIAL", "学", "sesion")
    assert fallo["dominado"] is False
    assert fecha(fallo["fecha"]).tzinfo is not None


def test_fallo_sin_codigo_error_funciona_como_antes(responder, sesion):
    datos = responder("学", False)

    assert datos["errores_frecuentes"] == {"学": 1}
    progreso = entidad(sesion)
    assert progreso.errores_por_codigo == {}
    assert progreso.historial_errores[0]["codigo"] is None


def test_el_historial_recuerda_si_el_caracter_estaba_dominado(responder, sesion):
    responder("学", True)
    responder("学", False, codigo_error="NO_SABE")
    responder("学", False, codigo_error="NO_SABE")

    assert [e["dominado"] for e in entidad(sesion).historial_errores] == [True, False]


@pytest.mark.parametrize("codigo", ["OTRO_CODIGO", "", "trazo_invertido", 7, True, ["NO_SABE"]])
def test_codigo_error_invalido_devuelve_400_y_no_guarda(client, sesion, codigo):
    resp = client.post(
        f"{URL}respuestas/", json={"caracter": "学", "acerto": False, "codigo_error": codigo}
    )

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"
    assert contar(sesion) == 0


def test_codigo_error_null_es_como_no_mandarlo(client, sesion):
    resp = client.post(
        f"{URL}respuestas/", json={"caracter": "学", "acerto": False, "codigo_error": None}
    )

    assert resp.status_code == 200
    assert entidad(sesion).historial_errores[0]["codigo"] is None


@pytest.mark.parametrize("codigo", ["PINYIN_INICIAL", "OTRO_CODIGO", 7])
def test_codigo_error_con_acierto_se_ignora(client, sesion, codigo):
    resp = client.post(
        f"{URL}respuestas/", json={"caracter": "学", "acerto": True, "codigo_error": codigo}
    )

    assert resp.status_code == 200
    progreso = entidad(sesion)
    assert progreso.historial_errores == []
    assert progreso.errores_por_codigo == {}


def test_la_respuesta_con_codigo_error_no_cambia_de_forma(client, responder):
    sin_codigo = responder("学", False)
    con_codigo = responder("校", False, codigo_error="NO_SABE")

    assert list(con_codigo) == list(sin_codigo)
    assert con_codigo == client.get(URL).get_json()


# ---------- POST /progreso/<usuario_id>/errores/ (página Trazos) ----------


def test_error_de_trazo_solo_alimenta_el_historial(client, responder, sesion):
    responder("人", True)
    responder("大", False)
    antes = client.get(URL).get_json()

    resp = client.post(f"{URL}errores/", json={"caracter": "人", "codigo_error": "TRAZO_INVERTIDO"})

    assert resp.status_code == 200
    assert resp.get_json() == {"usuario_id": USUARIO, "registrado": True}
    despues = client.get(URL).get_json()
    # Ni racha, ni dominados, ni errores frecuentes, ni tasa, ni repaso.
    for campo in antes:
        if campo != "actualizado_en":
            assert despues[campo] == antes[campo], campo
    progreso = entidad(sesion)
    # RF-IA-02: ni respuestas/ ni errores/ agendan.
    assert progreso.agenda_repaso == {}
    assert progreso.errores_por_codigo == {"TRAZO_INVERTIDO": 1}
    assert progreso.historial_errores[-1]["origen"] == "trazos"


def test_error_de_trazo_de_usuario_nuevo_crea_el_progreso_inicial(client, sesion):
    resp = client.post(f"{URL}errores/", json={"caracter": "人", "codigo_error": "TRAZO_CORTO"})

    assert resp.status_code == 200
    assert contar(sesion) == 1
    datos = client.get(URL).get_json()
    assert (datos["tasa_acierto"], datos["errores_frecuentes"], datos["proximo_repaso"]) == (0.5, {}, None)


def test_reintento_del_mismo_trazo_no_se_registra_dos_veces(client, sesion):
    cuerpo = {"caracter": "人", "codigo_error": "TRAZO_INVERTIDO"}

    assert client.post(f"{URL}errores/", json=cuerpo).get_json()["registrado"] is True
    assert client.post(f"{URL}errores/", json=cuerpo).get_json()["registrado"] is False

    assert len(entidad(sesion).historial_errores) == 1


@pytest.mark.parametrize("cuerpo", [
    {},
    {"caracter": "人"},
    {"codigo_error": "TRAZO_INVERTIDO"},
    {"caracter": "人", "codigo_error": None},
    {"caracter": "人", "codigo_error": "OTRO_CODIGO"},
    {"caracter": "人", "codigo_error": "PINYIN_INICIAL"},
    {"caracter": "人", "codigo_error": "TRAZO_AUTOCALIFICADO"},
    {"caracter": "人", "codigo_error": "NO_SABE"},
    {"caracter": "人" * 9, "codigo_error": "TRAZO_INVERTIDO"},
    ["人", "TRAZO_INVERTIDO"],
])
def test_error_de_trazo_invalido_devuelve_400_y_no_guarda(client, sesion, cuerpo):
    resp = client.post(f"{URL}errores/", json=cuerpo)

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"
    assert contar(sesion) == 0


def test_errores_solo_acepta_post(client):
    assert client.get(f"{URL}errores/").status_code == 405


# ---------- GET /progreso/<usuario_id>/patrones/ ----------


def test_patrones_de_usuario_nuevo_es_vacio_y_no_guarda(client, sesion):
    resp = client.get(f"{URL}patrones/")

    assert resp.status_code == 200
    assert resp.get_json() == {"usuario_id": USUARIO, "ventana_dias": 14, "patrones": []}
    assert contar(sesion) == 0


def test_dos_fallos_no_son_un_patron(client, responder):
    responder("学", False, codigo_error="PINYIN_INICIAL")
    responder("学", False, codigo_error="PINYIN_INICIAL")

    assert client.get(f"{URL}patrones/").get_json()["patrones"] == []


def test_patrones_por_tipo_de_error_y_por_caracter(client, responder):
    # Trazos: tres trazos al revés en caracteres distintos.
    for caracter in ("人", "大", "水"):
        client.post(f"{URL}errores/", json={"caracter": caracter, "codigo_error": "TRAZO_INVERTIDO"})
    # Sesión: el mismo carácter fallado cuatro veces.
    for _ in range(4):
        responder("学", False, codigo_error="TRAZO_AUTOCALIFICADO")

    patrones = client.get(f"{URL}patrones/").get_json()["patrones"]

    assert [p["codigo"] for p in patrones] == ["PATRON_CARACTER_RECURRENTE", "PATRON_TRAZO_INVERTIDO"]
    recurrente, invertido = patrones
    assert list(invertido) == [
        "codigo", "tipo", "frecuencia", "caracteres", "ultima_vez", "titulo", "consejo",
    ]
    assert (recurrente["tipo"], recurrente["frecuencia"], recurrente["caracteres"]) == ("caracter", 4, ["学"])
    assert (invertido["tipo"], invertido["frecuencia"]) == ("error", 3)
    assert sorted(invertido["caracteres"]) == sorted(["人", "大", "水"])
    assert invertido["titulo"] == "Trazos al revés"
    assert invertido["ultima_vez"].endswith("Z")


def test_patrones_usa_la_ventana_de_14_dias(sesion):
    usuario = uuid.UUID(USUARIO)
    ahora = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    for dias in (20, 16, 15):
        servicio.registrar_respuesta(
            sesion, usuario, "学", False, momento=ahora - timedelta(days=dias), codigo_error="NO_SABE"
        )

    assert servicio.detectar_patrones(sesion, usuario, momento=ahora) == []

    for dias in (3, 2, 1):
        servicio.registrar_respuesta(
            sesion, usuario, "校", False, momento=ahora - timedelta(days=dias), codigo_error="NO_SABE"
        )
    patrones = servicio.detectar_patrones(sesion, usuario, momento=ahora)
    assert [p.codigo for p in patrones] == ["PATRON_CARACTER_RECURRENTE", "PATRON_NO_SABE"]
    assert patrones[0].caracteres == ("校",)


def test_patrones_solo_acepta_get_y_valida_el_usuario(client):
    assert client.post(f"{URL}patrones/", json={}).status_code == 405
    resp = client.get("/api/v2/progreso/no-es-uuid/patrones/")
    assert (resp.status_code, resp.get_json()["codigo"]) == (400, "ENTRADA_INVALIDA")
