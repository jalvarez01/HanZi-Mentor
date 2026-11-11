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


def test_codigo_error_desconocido_en_espanol_y_en_ingles(client):
    url = f"/api/v2/progreso/{USUARIO}/respuestas/"
    cuerpo = {"caracter": "学", "acerto": False, "codigo_error": "OTRO"}

    es = client.post(url, json=cuerpo)
    en = client.post(url, json=cuerpo, headers=EN)

    assert es.get_json() == {
        "error": "El campo 'codigo_error' no es un código de error conocido",
        "codigo": "ENTRADA_INVALIDA",
    }
    assert en.get_json() == {
        "error": "The field 'codigo_error' is not a known error code",
        "codigo": "ENTRADA_INVALIDA",
    }


def test_error_de_trazo_con_codigo_de_pinyin_en_ingles(client):
    url = f"/api/v2/progreso/{USUARIO}/errores/"

    falta = client.post(url, json={"caracter": "人"}, headers=EN)
    pinyin = client.post(url, json={"caracter": "人", "codigo_error": "PINYIN_FINAL"}, headers=EN)

    assert falta.get_json()["error"] == "The field 'codigo_error' is required"
    assert pinyin.get_json()["error"] == "The field 'codigo_error' must be a stroke error code"


def test_patrones_traduce_titulo_y_consejo_pero_no_los_codigos(client):
    url = f"/api/v2/progreso/{USUARIO}/"
    for caracter in ("人", "大", "水"):
        client.post(f"{url}errores/", json={"caracter": caracter, "codigo_error": "TRAZO_INVERTIDO"})

    (es,) = client.get(f"{url}patrones/").get_json()["patrones"]
    (en,) = client.get(f"{url}patrones/", headers=EN).get_json()["patrones"]

    assert es["titulo"] == "Trazos al revés"
    assert es["consejo"] == (
        "Antes de trazar, mirá dónde empieza el modelo: casi siempre es de arriba "
        "hacia abajo y de izquierda a derecha."
    )
    assert en["titulo"] == "Strokes written backwards"
    assert en["consejo"] == (
        "Before you draw, look at where the model starts: almost always top to "
        "bottom and left to right."
    )
    for campo in ("codigo", "tipo", "frecuencia", "caracteres", "ultima_vez"):
        assert es[campo] == en[campo]


def test_todos_los_patrones_tienen_traduccion_al_ingles(app):
    from flask_babel import force_locale, gettext

    from dominio.patrones import CARACTER_RECURRENTE, PATRONES_DE_ERROR, RETROCESO

    textos = [t for _, titulo, consejo in (CARACTER_RECURRENTE, RETROCESO) for t in (titulo, consejo)]
    for definiciones in PATRONES_DE_ERROR.values():
        for _, titulo, consejo in definiciones.values():
            textos += [titulo, consejo]

    assert len(textos) == 22
    with app.test_request_context(), force_locale("en"):
        for texto in textos:
            assert gettext(texto) != texto, texto


def test_curva_olvido_invalida_en_espanol_y_en_ingles(client):
    url = f"/api/v2/progreso/{USUARIO}/curva-olvido/"
    sin_zona = {"sesion_id": 1, "cerrada_en": "2026-11-10T12:00:00", "respuestas": [{"caracter": "x", "acerto": True}]}

    es = client.post(url, json=sin_zona)
    en = client.post(url, json=sin_zona, headers=EN)

    assert es.get_json() == {
        "error": "El campo 'cerrada_en' debe ser una fecha ISO 8601 con zona horaria",
        "codigo": "ENTRADA_INVALIDA",
    }
    assert en.get_json() == {
        "error": "The field 'cerrada_en' must be an ISO 8601 date with a time zone",
        "codigo": "ENTRADA_INVALIDA",
    }


def test_curva_olvido_demas_mensajes_en_ingles(client):
    url = f"/api/v2/progreso/{USUARIO}/curva-olvido/"
    cierre = "2026-11-10T12:00:00+00:00"

    def error(cuerpo):
        return client.post(url, json=cuerpo, headers=EN).get_json()["error"]

    assert error({"sesion_id": 0}) == "The field 'sesion_id' must be a positive integer"
    assert error({"sesion_id": 1, "cerrada_en": cierre, "respuestas": []}) == (
        "The field 'respuestas' must be a list of 1 to 20 answers"
    )
    assert error({"sesion_id": 1, "cerrada_en": cierre, "respuestas": ["x"]}) == (
        "Each answer must be an object with 'caracter' and 'acerto'"
    )


def test_repasos_dias_invalido_en_ingles(client):
    resp = client.get(f"/api/v2/progreso/{USUARIO}/repasos/?dias=40", headers=EN)

    assert resp.get_json() == {
        "error": "The field 'dias' must be an integer between 1 and 30",
        "codigo": "ENTRADA_INVALIDA",
    }
