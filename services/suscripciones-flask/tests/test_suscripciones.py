"""Flujos completos por HTTP: activar, renovar, cancelar, vencer y pagos."""

from sqlalchemy import select

from modelos import Pago
from tests.conftest import NO_RESPONDE, OTRO, RECHAZADA, SIN_FONDOS, URL, USUARIO


def consultar(client, usuario=USUARIO):
    resp = client.get(f"/api/v2/suscripciones/{usuario}/")
    assert resp.status_code == 200
    return resp.get_json()


def pagos(client):
    return client.get(f"{URL}pagos/").get_json()["pagos"]


def test_usuario_nuevo_tiene_free(client):
    assert consultar(client) == {
        "usuario_id": USUARIO,
        "plan": "free",
        "nombre_plan": "Gratis",
        "estado": "activa",
        "vence_en": None,
        "nivel_maximo": 3,
        "acciones": ["activar"],
    }


def test_planes(client):
    cuerpo = client.get("/api/v2/suscripciones/planes/").get_json()

    assert cuerpo["pasarela"] == "simulada"
    assert [(p["codigo"], p["precio"], p["nivel_maximo"]) for p in cuerpo["planes"]] == [
        ("free", 0, 3),
        ("premium", 14900, 6),
    ]
    assert cuerpo["planes"][1]["periodo_dias"] == 30
    assert cuerpo["planes"][1]["moneda"] == "COP"


def test_activar_premium(client, activar):
    resp = activar()

    assert resp.status_code == 201
    cuerpo = resp.get_json()
    assert cuerpo["suscripcion"] == {
        "usuario_id": USUARIO,
        "plan": "premium",
        "nombre_plan": "Premium",
        "estado": "activa",
        "vence_en": "2026-12-11T15:00:00Z",
        "nivel_maximo": 6,
        "acciones": ["renovar", "cancelar"],
    }
    p = cuerpo["pago"]
    assert (p["concepto"], p["estado"], p["monto"], p["moneda"]) == ("activacion", "aprobado", 14900, "COP")
    assert (p["marca"], p["ultimos4"], p["pasarela"]) == ("visa", "4242", "simulada")
    assert p["referencia"].startswith("SIM-")
    assert consultar(client)["plan"] == "premium"


def test_la_tarjeta_no_se_guarda_ni_se_devuelve(app, activar):
    resp = activar()

    assert "4242424242424242" not in resp.get_data(as_text=True)
    assert not {"numero", "cvc", "titular", "vencimiento"} & set(resp.get_json()["pago"])
    with app.app_context():
        sesion = app.extensions["db"]["fabrica"]()
        (guardado,) = sesion.scalars(select(Pago)).all()
        valores = " ".join(str(getattr(guardado, c.key)) for c in Pago.__table__.columns)
        sesion.close()
    assert "4242424242424242" not in valores
    assert "Ana" not in valores


def test_activar_dos_veces_cobra_una_sola(client, activar):
    activar()
    resp = activar()

    assert resp.status_code == 409
    assert resp.get_json()["codigo"] == "YA_ES_PREMIUM"
    assert len(pagos(client)) == 1


def test_tarjeta_rechazada_no_activa_y_queda_en_el_historial(client, activar):
    resp = activar(RECHAZADA)

    assert resp.status_code == 402
    assert resp.get_json() == {"error": "El banco rechazó la tarjeta.", "codigo": "TARJETA_RECHAZADA"}
    assert consultar(client)["plan"] == "free"
    (rechazado,) = pagos(client)
    assert (rechazado["estado"], rechazado["codigo_rechazo"], rechazado["referencia"]) == (
        "rechazado", "TARJETA_RECHAZADA", None,
    )


def test_sin_fondos(client, activar):
    resp = activar(SIN_FONDOS)

    assert resp.status_code == 402
    assert resp.get_json()["codigo"] == "FONDOS_INSUFICIENTES"


def test_pasarela_no_responde_no_guarda_nada(client, activar):
    resp = activar(NO_RESPONDE)

    assert resp.status_code == 503
    assert resp.get_json()["codigo"] == "PASARELA_NO_DISPONIBLE"
    assert consultar(client)["plan"] == "free"
    assert pagos(client) == []


def test_reintentar_despues_de_un_rechazo(client, activar):
    activar(RECHAZADA)
    resp = activar()

    assert resp.status_code == 201
    assert [p["estado"] for p in pagos(client)] == ["aprobado", "rechazado"]


def test_cancelar_mantiene_premium_hasta_el_vencimiento(client, activar):
    activar()
    resp = client.post(f"{URL}cancelar/")

    assert resp.status_code == 200
    s = resp.get_json()["suscripcion"]
    assert (s["plan"], s["estado"], s["vence_en"]) == ("premium", "cancelada", "2026-12-11T15:00:00Z")
    assert s["acciones"] == ["renovar"]
    assert "pago" not in resp.get_json()

    otra = client.post(f"{URL}cancelar/")
    assert (otra.status_code, otra.get_json()["codigo"]) == (409, "YA_CANCELADA")


def test_free_no_cancela_ni_renueva(client, renovar):
    cancelar = client.post(f"{URL}cancelar/")
    renovacion = renovar()

    assert (cancelar.status_code, cancelar.get_json()["codigo"]) == (409, "SIN_PREMIUM")
    assert (renovacion.status_code, renovacion.get_json()["codigo"]) == (409, "SIN_PREMIUM")
    assert pagos(client) == []


def test_renovar_suma_30_dias_y_no_deja_renovar_dos_veces(client, activar, renovar, reloj):
    activar()
    reloj.avanzar(days=5)

    resp = renovar()

    assert resp.status_code == 200
    s = resp.get_json()["suscripcion"]
    assert s["vence_en"] == "2027-01-10T15:00:00Z"
    assert s["acciones"] == ["cancelar"]
    assert resp.get_json()["pago"]["concepto"] == "renovacion"

    doble = renovar()
    assert (doble.status_code, doble.get_json()["codigo"]) == (409, "RENOVACION_ANTICIPADA")
    assert len(pagos(client)) == 2


def test_renovar_una_cancelada_la_reactiva(client, activar, renovar):
    activar()
    client.post(f"{URL}cancelar/")

    s = renovar().get_json()["suscripcion"]

    assert (s["plan"], s["estado"]) == ("premium", "activa")
    assert s["acciones"] == ["cancelar"]


def test_renovacion_rechazada_no_cambia_nada(client, activar, renovar):
    activar()
    antes = consultar(client)

    resp = renovar(RECHAZADA)

    assert resp.status_code == 402
    assert consultar(client) == antes


def test_al_vencer_vuelve_a_free_y_se_puede_activar_otra_vez(client, activar, reloj):
    activar()
    client.post(f"{URL}cancelar/")
    reloj.avanzar(days=30)

    vencida = consultar(client)
    assert (vencida["plan"], vencida["estado"], vencida["nivel_maximo"]) == ("free", "vencida", 3)
    assert vencida["vence_en"] == "2026-12-11T15:00:00Z"
    assert vencida["acciones"] == ["activar"]

    resp = activar()
    assert resp.status_code == 201
    s = resp.get_json()["suscripcion"]
    assert (s["plan"], s["estado"], s["vence_en"]) == ("premium", "activa", "2027-01-10T15:00:00Z")


def test_cada_usuario_tiene_su_suscripcion(client, activar):
    activar()

    assert consultar(client, OTRO)["plan"] == "free"


def test_historial_del_mas_reciente_al_mas_antiguo(client, activar, renovar, reloj):
    activar()
    reloj.avanzar(days=1)
    renovar()

    assert [p["concepto"] for p in pagos(client)] == ["renovacion", "activacion"]


def test_entrada_invalida(client):
    sin_uuid = client.get("/api/v2/suscripciones/no-es-uuid/")
    plan_free = client.post(f"{URL}activar/", json={"plan": "free"})
    sin_cuerpo = client.post(f"{URL}renovar/", data="x", content_type="application/json")

    for resp in (sin_uuid, plan_free, sin_cuerpo):
        assert resp.status_code == 400
        assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"
