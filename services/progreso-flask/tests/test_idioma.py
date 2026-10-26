"""T22: Accept-Language elige el idioma del mensaje; las claves, el código y
el estado no cambian. Sin cabecera, o con otro idioma, en español."""

EN = {"Accept-Language": "en-US,en;q=0.9"}
USUARIO = "12345678-1234-5678-1234-567812345678"


def test_usuario_invalido_en_espanol_y_en_ingles(client):
    es = client.get("/api/v2/progreso/no-es-uuid/", headers={"Accept-Language": "es"})
    en = client.get("/api/v2/progreso/no-es-uuid/", headers=EN)
    fr = client.get("/api/v2/progreso/no-es-uuid/", headers={"Accept-Language": "fr"})

    assert (es.status_code, en.status_code, fr.status_code) == (400, 400, 400)
    assert es.get_json() == {"error": "El usuario_id debe ser un UUID válido", "codigo": "ENTRADA_INVALIDA"}
    assert en.get_json() == {"error": "The usuario_id must be a valid UUID", "codigo": "ENTRADA_INVALIDA"}
    assert fr.get_json() == es.get_json()


def test_caracter_largo_con_su_maximo(client):
    url = f"/api/v2/progreso/{USUARIO}/respuestas/"
    cuerpo = {"caracter": "学" * 9, "acerto": True}

    es = client.post(url, json=cuerpo)
    en = client.post(url, json=cuerpo, headers=EN)

    assert es.get_json()["error"] == "El campo 'caracter' admite hasta 8 caracteres"
    assert en.get_json()["error"] == "The field 'caracter' allows up to 8 characters"


def test_405_en_ingles(client):
    resp = client.delete(f"/api/v2/progreso/{USUARIO}/", headers=EN)

    assert resp.status_code == 405
    assert resp.get_json() == {"error": "Method not allowed", "codigo": "METODO_NO_PERMITIDO"}
