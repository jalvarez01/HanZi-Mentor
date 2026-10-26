"""T22: Accept-Language elige el idioma del mensaje; las claves, el código y
el estado no cambian. Sin cabecera, o con otro idioma, en español."""

from conftest import USUARIO

EN = {"Accept-Language": "en-US,en;q=0.9"}


def test_nivel_bloqueado_en_espanol_y_en_ingles(client):
    cuerpo = {"usuario_id": str(USUARIO), "nivel_hsk": 5}

    es = client.post("/api/v2/sesiones/", json=cuerpo, headers={"Accept-Language": "es"})
    en = client.post("/api/v2/sesiones/", json=cuerpo, headers=EN)
    fr = client.post("/api/v2/sesiones/", json=cuerpo, headers={"Accept-Language": "fr"})

    assert (es.status_code, en.status_code, fr.status_code) == (400, 400, 400)
    assert es.get_json() == {
        "error": "HSK5 aún no está desbloqueado (máximo actual: HSK2).",
        "codigo": "NIVEL_NO_PERMITIDO",
    }
    assert en.get_json() == {
        "error": "HSK5 is not unlocked yet (current maximum: HSK2).",
        "codigo": "NIVEL_NO_PERMITIDO",
    }
    assert fr.get_json() == es.get_json()


def test_ejercicio_ya_respondido_en_ingles(client, crear_sesion):
    ejercicio = crear_sesion()["ejercicios"][0]["id"]
    url = f"/api/v2/ejercicios/{ejercicio}/responder/"
    client.post(url, json={"acerto": True})

    resp = client.post(url, json={"acerto": True}, headers=EN)

    assert resp.status_code == 409
    assert resp.get_json() == {
        "error": f"Exercise {ejercicio} has already been answered.",
        "codigo": "EJERCICIO_YA_RESPONDIDO",
    }


def test_validacion_en_ingles(client):
    resp = client.post("/api/v2/sesiones/", json={"usuario_id": str(USUARIO), "nivel_hsk": 9}, headers=EN)

    assert resp.get_json() == {
        "error": "The field 'nivel_hsk' must be an integer between 1 and 6",
        "codigo": "ENTRADA_INVALIDA",
    }


def test_aviso_en_ingles_con_las_mismas_claves(client, crear_sesion, progreso):
    ejercicios = crear_sesion()["ejercicios"]
    progreso.caido = True

    es = client.post(f"/api/v2/ejercicios/{ejercicios[0]['id']}/responder/", json={"acerto": True}).get_json()
    en = client.post(
        f"/api/v2/ejercicios/{ejercicios[1]['id']}/responder/", json={"acerto": True}, headers=EN
    ).get_json()

    assert list(es) == list(en)
    assert es["aviso"].startswith("La respuesta quedó guardada")
    assert en["aviso"] == (
        "The answer was saved in the session, but the progress could not be updated: "
        "the progress service did not respond."
    )
