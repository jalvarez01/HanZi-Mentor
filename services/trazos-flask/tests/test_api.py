"""Pruebas del contrato HTTP del microservicio."""

import pytest

from app import create_app

URL = "/api/v2/trazos/validar/"

# Trazo diagonal, equivalente al primero del carácter 人 (sistema 1024).
MEDIANA = [[458, 800], [435, 764], [400, 700], [350, 620], [300, 540]]
ANCHO = ALTO = 300
LIENZO = 1024
DESPLAZAMIENTO_Y = 900

CAMPOS_200 = {"aprobado", "puntaje", "motivo", "detalle", "invertido", "puntos_lejanos"}


def a_canvas(punto):
    x, y = punto
    return [x / LIENZO * ANCHO, (DESPLAZAMIENTO_Y - y) / LIENZO * ALTO]


def densificar(puntos, por_segmento=40):
    resultado = []
    for a, b in zip(puntos, puntos[1:]):
        for t in range(por_segmento):
            f = t / por_segmento
            resultado.append([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f])
    resultado.append(puntos[-1])
    return resultado


def cuerpo(invertir=False, **cambios):
    base = list(reversed(MEDIANA)) if invertir else MEDIANA
    datos = {
        "mediana": MEDIANA,
        "puntos": [a_canvas(p) for p in densificar(base)],
        "ancho": ANCHO,
        "alto": ALTO,
    }
    datos.update(cambios)
    return datos


@pytest.fixture
def client():
    return create_app({"TESTING": True}).test_client()


def assert_error_json(resp, estado, codigo):
    assert resp.status_code == estado
    assert resp.is_json
    assert resp.get_json()["codigo"] == codigo
    assert "error" in resp.get_json()


def test_trazo_correcto(client):
    resp = client.post(URL, json=cuerpo())

    assert resp.status_code == 200
    datos = resp.get_json()
    assert set(datos) == CAMPOS_200
    assert datos["aprobado"] is True
    assert datos["motivo"] == "correcto"
    assert datos["puntaje"] >= 95
    assert datos["invertido"] is False


def test_trazo_invertido(client):
    resp = client.post(URL, json=cuerpo(invertir=True))

    assert resp.status_code == 200
    datos = resp.get_json()
    assert datos["aprobado"] is False
    assert datos["invertido"] is True
    assert datos["motivo"] == "invertido"


def test_acepta_puntos_como_objetos(client):
    puntos = [{"x": x, "y": y} for x, y in cuerpo()["puntos"]]
    resp = client.post(URL, json=cuerpo(puntos=puntos))

    assert resp.status_code == 200
    assert resp.get_json()["aprobado"] is True


def test_json_mal_formado(client):
    resp = client.post(URL, data="{no es json", content_type="application/json")
    assert_error_json(resp, 400, "ENTRADA_INVALIDA")


def test_cuerpo_que_no_es_objeto(client):
    resp = client.post(URL, json=[1, 2, 3])
    assert_error_json(resp, 400, "ENTRADA_INVALIDA")


def test_falta_un_campo(client):
    datos = cuerpo()
    del datos["alto"]

    resp = client.post(URL, json=datos)

    assert_error_json(resp, 400, "ENTRADA_INVALIDA")
    assert "alto" in resp.get_json()["error"]


def test_puntos_insuficientes(client):
    resp = client.post(URL, json=cuerpo(puntos=[[1, 1]]))
    assert_error_json(resp, 400, "ENTRADA_INVALIDA")


def test_punto_no_numerico(client):
    resp = client.post(URL, json=cuerpo(puntos=[[1, 2], ["a", 3]]))
    assert_error_json(resp, 400, "ENTRADA_INVALIDA")


@pytest.mark.parametrize("valor", [-300, 0, 1.5, "300", True])
def test_ancho_invalido(client, valor):
    resp = client.post(URL, json=cuerpo(ancho=valor))
    assert_error_json(resp, 400, "ENTRADA_INVALIDA")


def test_health(client):
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.get_json() == {"estado": "ok", "servicio": "trazos-flask"}


def test_metodo_no_permitido(client):
    resp = client.get(URL)
    assert_error_json(resp, 405, "METODO_NO_PERMITIDO")


def test_ruta_inexistente_devuelve_json(client):
    resp = client.get("/no/existe")
    assert_error_json(resp, 404, "NO_ENCONTRADO")


def test_error_inesperado_no_filtra_detalles(client, monkeypatch):
    def falla(_solicitud):
        raise RuntimeError("secreto interno")

    monkeypatch.setattr("rutas.validar_trazo", falla)

    resp = client.post(URL, json=cuerpo())

    assert resp.status_code == 500
    assert resp.get_json() == {"error": "Error interno", "codigo": "ERROR_INTERNO"}
    assert "secreto" not in resp.get_data(as_text=True)


# ---------- idioma de los mensajes (T22) ----------


def test_validacion_en_espanol_y_en_ingles(client):
    sin_alto = {k: v for k, v in cuerpo().items() if k != "alto"}

    es = client.post(URL, json=sin_alto, headers={"Accept-Language": "es"})
    en = client.post(URL, json=sin_alto, headers={"Accept-Language": "en-US,en;q=0.9"})

    assert (es.status_code, en.status_code) == (400, 400)
    assert es.get_json() == {"error": "Faltan campos: alto", "codigo": "ENTRADA_INVALIDA"}
    assert en.get_json() == {"error": "Missing fields: alto", "codigo": "ENTRADA_INVALIDA"}


def test_el_detalle_del_veredicto_se_traduce(client):
    es = client.post(URL, json=cuerpo()).get_json()
    en = client.post(URL, json=cuerpo(), headers={"Accept-Language": "en"}).get_json()

    # Mismas claves y mismo veredicto; solo cambia el texto del detalle.
    assert list(es) == list(en)
    assert {k: v for k, v in es.items() if k != "detalle"} == {k: v for k, v in en.items() if k != "detalle"}
    assert es["detalle"] == "Trazo correcto."
    assert en["detalle"] == "Correct stroke."


def test_punto_invalido_con_indice_en_ingles(client):
    resp = client.post(URL, json=cuerpo(puntos=[[0, 0], ["a", 1]]), headers={"Accept-Language": "en"})

    assert resp.get_json()["error"] == "'puntos[1]' has non-numeric coordinates"


def test_404_en_ingles(client):
    resp = client.get("/no/existe", headers={"Accept-Language": "en"})

    assert resp.get_json() == {"error": "Resource not found", "codigo": "NO_ENCONTRADO"}
