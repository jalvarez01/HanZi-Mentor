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


def test_acertar_crea_el_progreso_y_agenda_repaso(responder, sesion):
    antes = datetime.now(timezone.utc)

    datos = responder("学", True)

    assert contar(sesion) == 1
    assert datos["proximo_repaso"] is not None
    assert fecha(datos["proximo_repaso"]) >= antes + timedelta(days=1)
    assert datos["actualizado_en"] is not None


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
    momento = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)

    servicio.registrar_respuesta(sesion, uuid.UUID(USUARIO), "学", True, momento=momento)
    servicio.registrar_respuesta(sesion, uuid.UUID(USUARIO), "校", False, momento=momento)

    progreso = sesion.scalars(select(ProgresoUsuario)).one()
    assert progreso.agenda_repaso == {
        "学": "2026-10-24T12:00:00+00:00",
        "校": "2026-10-24T00:00:00+00:00",
    }
    # El más cercano de la agenda.
    assert progreso.proximo_repaso == momento + timedelta(hours=12)


def test_el_intervalo_crece_con_la_racha(sesion):
    momento = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    for _ in range(3):
        servicio.registrar_respuesta(sesion, uuid.UUID(USUARIO), "学", True, momento=momento)

    progreso = sesion.scalars(select(ProgresoUsuario)).one()
    # Tercer acierto seguido: 7 días.
    assert progreso.agenda_repaso["学"] == "2026-10-30T12:00:00+00:00"


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
