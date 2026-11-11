"""Accept-Language elige el idioma de los textos; claves, códigos y estados no cambian."""

from pathlib import Path

from babel.messages.extract import extract_from_dir
from babel.messages.pofile import read_po

from tests.conftest import EN, RECHAZADA, URL, pago

RAIZ = Path(__file__).resolve().parents[1]


def test_error_de_validacion_en_ingles(client):
    cuerpo = {"plan": "premium", "pago": pago(vencimiento="10/26")}

    es = client.post(f"{URL}activar/", json=cuerpo)
    en = client.post(f"{URL}activar/", json=cuerpo, headers=EN)
    fr = client.post(f"{URL}activar/", json=cuerpo, headers={"Accept-Language": "fr"})

    assert es.get_json() == {"error": "La tarjeta está vencida", "codigo": "ENTRADA_INVALIDA"}
    assert en.get_json() == {"error": "The card has expired", "codigo": "ENTRADA_INVALIDA"}
    assert fr.get_json() == es.get_json()


def test_titular_con_sus_limites_en_ingles(client):
    resp = client.post(f"{URL}activar/", json={"plan": "premium", "pago": pago(titular="A")}, headers=EN)

    assert resp.get_json()["error"] == "The cardholder name must have between 2 and 60 characters"


def test_pago_rechazado_en_ingles(client):
    resp = client.post(f"{URL}activar/", json={"plan": "premium", "pago": pago(RECHAZADA)}, headers=EN)

    assert resp.status_code == 402
    assert resp.get_json() == {"error": "The bank declined the card.", "codigo": "TARJETA_RECHAZADA"}


def test_renovacion_anticipada_con_los_dias(client, activar, renovar):
    activar()
    renovar()

    resp = client.post(f"{URL}renovar/", json={"pago": pago()}, headers=EN)

    assert resp.get_json()["error"] == (
        "You can only renew when 30 days or fewer are left before it expires."
    )


def test_planes_y_nombre_del_plan_en_ingles(client):
    planes = client.get("/api/v2/suscripciones/planes/", headers=EN).get_json()["planes"]
    actual = client.get(URL, headers=EN).get_json()

    assert [p["nombre"] for p in planes] == ["Free", "Premium"]
    assert planes[0]["descripcion"] == "Practice HSK levels 1 to 3."
    assert (actual["plan"], actual["nombre_plan"]) == ("free", "Free")


def test_todos_los_textos_tienen_traduccion_al_ingles():
    marcados = {
        mensaje
        for _, _, mensaje, _, _ in extract_from_dir(
            str(RAIZ),
            method_map=[("tests/**.py", "ignore"), ("**.py", "python")],
            keywords={"N_": None},
        )
    }
    with (RAIZ / "translations/en/LC_MESSAGES/messages.po").open("rb") as archivo:
        catalogo = read_po(archivo)
    traducidos = {m.id for m in catalogo if m.id and m.string}

    assert len(marcados) == 25
    assert marcados - traducidos == set()
