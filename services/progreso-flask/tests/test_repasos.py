"""Endpoints de RF-IA-02: POST .../curva-olvido/ y GET .../repasos/."""

import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

import servicio
from app import create_app
from modelos import ProgresoUsuario, SesionAplicada
from repositorio import ProgresoRepositorio
from tests.conftest import USUARIO

URL = f"/api/v2/progreso/{USUARIO}/"
CIERRE = "2026-11-10T12:00:00+00:00"


def cuerpo(sesion_id=1, cerrada_en=CIERRE, respuestas=None):
    return {
        "sesion_id": sesion_id,
        "cerrada_en": cerrada_en,
        "respuestas": respuestas if respuestas is not None else [
            {"caracter": "学", "acerto": True},
            {"caracter": "校", "acerto": False, "codigo_error": "PINYIN_FINAL"},
            {"caracter": "人", "acerto": False, "codigo_error": "NO_SABE"},
        ],
    }


def entidad(sesion):
    return sesion.scalars(select(ProgresoUsuario)).one()


def contar_aplicadas(sesion):
    return sesion.scalar(select(func.count()).select_from(SesionAplicada))


# ---------- POST .../curva-olvido/ ----------


def test_aplica_la_curva_y_responde_los_repasos(client, sesion):
    resp = client.post(f"{URL}curva-olvido/", json=cuerpo())

    assert resp.status_code == 200
    assert resp.get_json() == {
        "usuario_id": USUARIO,
        "sesion_id": 1,
        "aplicada": True,
        "repasos": [
            {"caracter": "学", "proximo_repaso": "2026-11-11T12:00:00Z", "intervalo_dias": 1, "repeticiones": 1},
            {"caracter": "校", "proximo_repaso": "2026-11-11T00:00:00Z", "intervalo_dias": 0, "repeticiones": 0},
            {"caracter": "人", "proximo_repaso": "2026-11-11T00:00:00Z", "intervalo_dias": 0, "repeticiones": 0},
        ],
    }
    progreso = entidad(sesion)
    assert progreso.curva_olvido == {
        "学": {"facilidad": 2.5, "repeticiones": 1, "intervalo_dias": 1},
        "校": {"facilidad": 2.18, "repeticiones": 0, "intervalo_dias": 0},
        "人": {"facilidad": 1.7, "repeticiones": 0, "intervalo_dias": 0},
    }
    assert client.get(URL).get_json()["proximo_repaso"] == "2026-11-11T00:00:00Z"


def test_la_misma_sesion_dos_veces_no_cambia_nada(client, sesion):
    primera = client.post(f"{URL}curva-olvido/", json=cuerpo())
    antes = entidad(sesion)
    estado = (dict(antes.agenda_repaso), dict(antes.curva_olvido))
    sesion.expire_all()

    # Mismo sesion_id, aunque llegue con otras respuestas o a otra hora.
    otra = cuerpo(cerrada_en="2026-11-20T12:00:00+00:00", respuestas=[{"caracter": "学", "acerto": False}])
    segunda = client.post(f"{URL}curva-olvido/", json=otra)

    assert primera.get_json()["aplicada"] is True
    assert segunda.status_code == 200
    assert segunda.get_json() == {"usuario_id": USUARIO, "sesion_id": 1, "aplicada": False, "repasos": []}
    despues = entidad(sesion)
    assert (despues.agenda_repaso, despues.curva_olvido) == estado
    assert contar_aplicadas(sesion) == 1


def test_otra_sesion_si_se_aplica(client):
    client.post(f"{URL}curva-olvido/", json=cuerpo(sesion_id=1))

    resp = client.post(f"{URL}curva-olvido/", json=cuerpo(
        sesion_id=2, cerrada_en="2026-11-11T12:00:00+00:00", respuestas=[{"caracter": "学", "acerto": True}],
    ))

    assert resp.get_json()["aplicada"] is True
    assert resp.get_json()["repasos"][0]["intervalo_dias"] == 6


def test_la_misma_sesion_de_otro_usuario_es_otra(client):
    otro = "87654321-4321-8765-4321-876543218765"
    client.post(f"{URL}curva-olvido/", json=cuerpo())

    resp = client.post(f"/api/v2/progreso/{otro}/curva-olvido/", json=cuerpo())

    assert resp.get_json()["aplicada"] is True


def test_cierre_concurrente_la_segunda_ve_la_sesion_ya_aplicada(app, sesion, monkeypatch):
    """Dos llamadas de la misma sesión que pasan a la vez el primer control:
    la clave primaria hace fallar a la segunda, que se reintenta y responde
    sin aplicar. Se simula forzando el control a False una vez."""
    usuario = uuid.UUID(USUARIO)
    cierre = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    respuestas = [{"caracter": "学", "acerto": True, "codigo_error": None}]

    assert servicio.aplicar_curva_olvido(sesion, usuario, 7, cierre, respuestas) is not None
    agenda = dict(entidad(sesion).agenda_repaso)

    original = ProgresoRepositorio.sesion_aplicada
    llamadas = {"n": 0}

    def no_la_ve_la_primera_vez(self, usuario_id, sesion_id):
        llamadas["n"] += 1
        return False if llamadas["n"] <= 2 else original(self, usuario_id, sesion_id)

    monkeypatch.setattr(ProgresoRepositorio, "sesion_aplicada", no_la_ve_la_primera_vez)
    otra = app.extensions["db"]["fabrica"]()
    resultado = servicio.aplicar_curva_olvido(otra, usuario, 7, cierre + timedelta(days=9), respuestas)
    otra.close()

    assert resultado is None
    sesion.expire_all()
    assert entidad(sesion).agenda_repaso == agenda
    assert contar_aplicadas(sesion) == 1


def test_dos_hilos_con_la_misma_sesion_la_aplican_una_vez(tmp_path):
    """Dos peticiones reales a la vez sobre una base en archivo."""
    url = f"sqlite:///{(tmp_path / 'concurrencia.sqlite3').as_posix()}"
    app = create_app({"TESTING": True, "DATABASE_URL": url})
    # La primera respuesta crea el progreso: así las dos compiten solo por la sesión.
    app.test_client().post(f"{URL}respuestas/", json={"caracter": "学", "acerto": True})

    resultados = []
    barrera = threading.Barrier(2)

    def llamar():
        barrera.wait()
        resultados.append(app.test_client().post(f"{URL}curva-olvido/", json=cuerpo()).get_json()["aplicada"])

    hilos = [threading.Thread(target=llamar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert sorted(resultados) == [False, True]
    sesion = app.extensions["db"]["fabrica"]()
    assert contar_aplicadas(sesion) == 1
    sesion.close()
    app.extensions["db"]["engine"].dispose()


def test_un_usuario_sin_progreso_lo_crea(client, sesion):
    resp = client.post(f"{URL}curva-olvido/", json=cuerpo())

    assert resp.get_json()["aplicada"] is True
    progreso = entidad(sesion)
    assert progreso.tasa_acierto == 0.5
    assert progreso.aciertos_consecutivos == {}


def test_la_curva_no_cambia_racha_tasa_ni_errores(client, responder):
    responder("学", True)
    responder("校", False)
    antes = client.get(URL).get_json()

    client.post(f"{URL}curva-olvido/", json=cuerpo())

    despues = client.get(URL).get_json()
    for campo in ("tasa_acierto", "aciertos_consecutivos", "errores_frecuentes", "caracteres_dominados"):
        assert despues[campo] == antes[campo], campo


def test_codigo_error_con_acierto_se_ignora(client):
    resp = client.post(f"{URL}curva-olvido/", json=cuerpo(respuestas=[
        {"caracter": "学", "acerto": True, "codigo_error": "OTRO"},
    ]))

    assert resp.status_code == 200
    assert resp.get_json()["repasos"][0]["intervalo_dias"] == 1


@pytest.mark.parametrize("datos", [
    None,
    ["no", "es", "objeto"],
    {"cerrada_en": CIERRE, "respuestas": [{"caracter": "学", "acerto": True}]},
    cuerpo(sesion_id=0),
    cuerpo(sesion_id=-3),
    cuerpo(sesion_id="7"),
    cuerpo(sesion_id=True),
    cuerpo(sesion_id=1.5),
    cuerpo(cerrada_en=None),
    cuerpo(cerrada_en="ayer"),
    cuerpo(cerrada_en="2026-11-10T12:00:00"),        # sin zona horaria
    cuerpo(cerrada_en=1731240000),
    cuerpo(respuestas=[]),
    cuerpo(respuestas=[{"caracter": "学", "acerto": True}] * 21),
    cuerpo(respuestas="学"),
    cuerpo(respuestas=["学"]),
    cuerpo(respuestas=[{"acerto": True}]),
    cuerpo(respuestas=[{"caracter": "学" * 9, "acerto": True}]),
    cuerpo(respuestas=[{"caracter": "学"}]),
    cuerpo(respuestas=[{"caracter": "学", "acerto": "si"}]),
    cuerpo(respuestas=[{"caracter": "学", "acerto": False, "codigo_error": "OTRO"}]),
])
def test_cuerpo_invalido_devuelve_400_y_no_guarda(client, sesion, datos):
    resp = client.post(f"{URL}curva-olvido/", json=datos)

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"
    assert sesion.scalar(select(func.count()).select_from(ProgresoUsuario)) == 0
    assert contar_aplicadas(sesion) == 0


def test_curva_olvido_valida_el_usuario_y_el_metodo(client):
    resp = client.post("/api/v2/progreso/no-es-uuid/curva-olvido/", json=cuerpo())
    assert (resp.status_code, resp.get_json()["codigo"]) == (400, "ENTRADA_INVALIDA")
    assert client.get(f"{URL}curva-olvido/").status_code == 405


# ---------- GET .../repasos/ ----------


def test_repasos_de_usuario_nuevo_es_vacio_y_no_guarda(client, sesion):
    resp = client.get(f"{URL}repasos/")

    datos = resp.get_json()
    assert resp.status_code == 200
    assert list(datos) == ["usuario_id", "momento", "dias", "vencidos", "proximos"]
    assert (datos["usuario_id"], datos["dias"], datos["vencidos"], datos["proximos"]) == (USUARIO, 7, [], [])
    assert datos["momento"].endswith("Z")
    assert sesion.scalar(select(func.count()).select_from(ProgresoUsuario)) == 0


def test_repasos_separa_vencidos_y_proximos(client):
    ahora = datetime.now(timezone.utc).replace(microsecond=0)
    # Una sesión cerrada hace 3 días: 校 y 人 (fallos, 12 h) ya vencieron;
    # 学 (acierto, 1 día) también.
    client.post(f"{URL}curva-olvido/", json=cuerpo(sesion_id=1, cerrada_en=(ahora - timedelta(days=3)).isoformat()))
    # Otra cerrada ahora: 大 a 1 día.
    client.post(f"{URL}curva-olvido/", json=cuerpo(
        sesion_id=2, cerrada_en=ahora.isoformat(), respuestas=[{"caracter": "大", "acerto": True}],
    ))

    datos = client.get(f"{URL}repasos/").get_json()

    assert [r["caracter"] for r in datos["vencidos"]] == ["人", "校", "学"]
    assert [r["caracter"] for r in datos["proximos"]] == ["大"]
    assert datos["proximos"][0] == {
        "caracter": "大",
        "proximo_repaso": (ahora + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "intervalo_dias": 1,
        "repeticiones": 1,
    }
    limitado = client.get(f"{URL}repasos/?limite=1").get_json()
    assert [r["caracter"] for r in limitado["vencidos"]] == ["人"]


def test_repasos_respeta_la_ventana_de_dias(client):
    ahora = datetime.now(timezone.utc)
    client.post(f"{URL}curva-olvido/", json=cuerpo(sesion_id=1, cerrada_en=ahora.isoformat(),
                                                   respuestas=[{"caracter": "学", "acerto": True}]))
    client.post(f"{URL}curva-olvido/", json=cuerpo(sesion_id=2, cerrada_en=ahora.isoformat(),
                                                   respuestas=[{"caracter": "学", "acerto": True}]))
    # 学 queda a 6 días.

    assert client.get(f"{URL}repasos/?dias=5").get_json()["proximos"] == []
    assert [r["caracter"] for r in client.get(f"{URL}repasos/?dias=7").get_json()["proximos"]] == ["学"]


@pytest.mark.parametrize("consulta", ["dias=0", "dias=31", "dias=abc", "dias=", "limite=0", "limite=51", "limite=x"])
def test_repasos_parametros_invalidos_devuelven_400(client, consulta):
    resp = client.get(f"{URL}repasos/?{consulta}")

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"


def test_repasos_solo_acepta_get_y_valida_el_usuario(client):
    assert client.post(f"{URL}repasos/", json={}).status_code == 405
    assert client.get("/api/v2/progreso/no-es-uuid/repasos/").status_code == 400


# ---------- respuestas/ ya no agenda ----------


def test_responder_un_caracter_con_agenda_anterior_fija_su_estado_sin_tocar_la_fecha(sesion):
    usuario = uuid.UUID(USUARIO)
    fecha_vieja = "2026-11-12T10:00:00+00:00"
    sesion.add(ProgresoUsuario(
        usuario_id=usuario, aciertos_consecutivos={"人": 3}, agenda_repaso={"人": fecha_vieja},
    ))
    sesion.commit()

    servicio.registrar_respuesta(sesion, usuario, "人", True)

    progreso = entidad(sesion)
    assert progreso.agenda_repaso == {"人": fecha_vieja}
    assert progreso.curva_olvido == {"人": {"facilidad": 2.5, "repeticiones": 3, "intervalo_dias": 7}}
    assert progreso.aciertos_consecutivos == {"人": 4}
