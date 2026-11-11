"""Estándar común de los servicios Flask: health y errores siempre en JSON."""

from app import create_app


def test_health(client):
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.get_json() == {"estado": "ok", "servicio": "suscripciones-flask"}


def test_404_en_json(client):
    resp = client.get("/api/v2/suscripciones/")

    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Recurso no encontrado", "codigo": "NO_ENCONTRADO"}


def test_405_en_json(client):
    resp = client.delete("/api/v2/suscripciones/planes/")

    assert resp.status_code == 405
    assert resp.get_json()["codigo"] == "METODO_NO_PERMITIDO"


def test_error_inesperado_no_muestra_el_detalle():
    app = create_app({"TESTING": False, "DATABASE_URL": "sqlite://"})

    @app.get("/falla")
    def falla():
        raise RuntimeError("secreto interno")

    resp = app.test_client().get("/falla")

    assert resp.status_code == 500
    assert resp.get_json() == {"error": "Error interno", "codigo": "ERROR_INTERNO"}
    assert "secreto" not in resp.get_data(as_text=True)


def test_pasarela_desconocida_no_arranca():
    import pytest

    with pytest.raises(ValueError, match="PASARELA_PAGO desconocida"):
        create_app({"DATABASE_URL": "sqlite://", "PASARELA_PAGO": "otra"})
