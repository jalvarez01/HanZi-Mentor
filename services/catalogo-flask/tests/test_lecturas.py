"""Varias lecturas en pinyin: tabla de Unihan, carga, detalle, migración de
bases anteriores y relleno al arrancar."""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

import cargar
import lecturas
from app import create_app
from carga import cargar as cargar_datos
from carga import completar_lecturas
from hsk import CARACTERES_POR_NIVEL
from lecturas import lecturas_de

DATOS = Path(__file__).parent / "datos" / "lecturas"
TABLA = json.loads(lecturas.ARCHIVO.read_text(encoding="utf-8"))


# ---------- datos/lecturas_hsk.json ----------


def test_la_tabla_cubre_todos_los_caracteres_hsk():
    hsk = {h for caracteres in CARACTERES_POR_NIVEL.values() for h in caracteres}

    assert set(TABLA["lecturas"]) == hsk
    assert sum(TABLA["conteo"].values()) == len(hsk)
    assert all(TABLA["lecturas"][h] for h in hsk)


def test_la_tabla_dice_su_fuente_y_su_licencia():
    assert "Unicode Unihan 17.0.0" in TABLA["fuente"]
    assert "kXHC1983" in TABLA["fuente"]
    assert "Unicode License v3" in TABLA["licencia"]
    assert TABLA["generado_con"] == "scripts/generar_lecturas.py"


@pytest.mark.parametrize("hanzi, propias, esperadas", [
    ("长", ["zhǎng"], ["zhǎng", "cháng"]),
    ("得", ["dé"], ["dé", "de", "děi"]),
    ("了", ["le", "liǎo"], ["le", "liǎo", "liào"]),
    ("人", ["rén"], ["rén"]),
])
def test_lecturas_con_la_de_make_me_a_hanzi_primero(hanzi, propias, esperadas):
    assert lecturas_de(hanzi, propias) == esperadas


def test_un_caracter_fuera_de_la_tabla_queda_con_las_propias():
    assert lecturas_de("丶", ["zhǔ"]) == ["zhǔ"]
    assert lecturas_de("丶") == []


def test_el_generador_lee_kxhc1983_sin_repetidas_y_con_respaldos():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "generar_lecturas", lecturas.ARCHIVO.parents[1] / "scripts" / "generar_lecturas.py"
    )
    generador = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generador)

    assert generador.lecturas_xhc("0121.040:cháng 1456.020:zhǎng") == ["cháng", "zhǎng"]
    assert generador.lecturas_xhc("0001.010,0002.020:a 0003.030*:a 0004.040:b") == ["a", "b"]
    unihan = {"长": {"kXHC1983": ["cháng", "zhǎng"]}, "得": {"kMandarin": ["dé"]}}
    resultado = generador.generar(unihan, {"长": ["zhǎng"], "人": ["rén"]}, "17.0.0")
    assert resultado["lecturas"]["长"] == ["zhǎng", "cháng"]
    assert resultado["lecturas"]["得"] == ["dé"]
    assert resultado["lecturas"]["人"] == ["rén"]
    assert resultado["conteo"]["kXHC1983"] == 1
    assert resultado["conteo"]["kMandarin"] == 1
    assert resultado["conteo"]["makemeahanzi"] == 1


# ---------- carga y API ----------


def test_la_carga_guarda_todas_las_lecturas_y_deja_el_pinyin(sesion):
    cargar_datos(sesion, DATOS, todos=True)

    from modelos import Caracter
    guardados = {c.hanzi: (c.pinyin, c.lecturas) for c in sesion.query(Caracter)}
    assert guardados["长"] == ("zhǎng", ["zhǎng", "cháng"])
    assert guardados["得"] == ("dé", ["dé", "de", "děi"])
    assert guardados["了"] == ("le", ["le", "liǎo", "liào"])
    assert guardados["人"] == ("rén", ["rén"])


def test_el_detalle_expone_lecturas_y_la_lista_no(client, sesion):
    cargar_datos(sesion, DATOS, todos=True)

    detalle = client.get("/api/v2/caracteres/长/").get_json()
    lista = client.get("/api/v2/caracteres/?nivel=2").get_json()["caracteres"]

    assert detalle["pinyin"] == "zhǎng"
    assert detalle["lecturas"] == ["zhǎng", "cháng"]
    assert list(detalle)[-1] == "lecturas"
    assert all("lecturas" not in c for c in lista)


def test_un_caracter_de_una_sola_lectura(client, sesion):
    cargar_datos(sesion, DATOS, todos=True)

    assert client.get("/api/v2/caracteres/人/").get_json()["lecturas"] == ["rén"]


# ---------- bases anteriores a la columna ----------


ESQUEMA_VIEJO = """
CREATE TABLE caracteres (
    id INTEGER PRIMARY KEY, hanzi VARCHAR(4) UNIQUE, pinyin VARCHAR(64),
    definicion TEXT, radical VARCHAR(4), descomposicion VARCHAR(64),
    nivel_hsk SMALLINT, frecuencia INTEGER
)
"""


@pytest.fixture
def base_vieja(tmp_path):
    url = f"sqlite:///{tmp_path / 'vieja.sqlite3'}"
    engine = create_engine(url)
    with engine.begin() as conexion:
        conexion.execute(text(ESQUEMA_VIEJO))
        conexion.execute(text(
            "INSERT INTO caracteres (hanzi, pinyin, definicion, radical, descomposicion, nivel_hsk) "
            "VALUES ('长', 'zhǎng', 'long', '长', '', 2), ('人', 'rén', 'man', '人', '', 1)"
        ))
    engine.dispose()
    return url


def test_el_arranque_agrega_la_columna_y_el_detalle_usa_el_pinyin(base_vieja):
    app = create_app({"TESTING": True, "DATABASE_URL": base_vieja})

    columnas = {c["name"] for c in inspect(app.extensions["db"]["engine"]).get_columns("caracteres")}
    detalle = app.test_client().get("/api/v2/caracteres/长/").get_json()

    assert "lecturas" in columnas
    # Antes de completar, el detalle no se rompe: usa el pinyin guardado.
    assert detalle["lecturas"] == ["zhǎng"]


def test_completar_lecturas_rellena_sin_dataset_y_es_idempotente(base_vieja):
    app = create_app({"TESTING": True, "DATABASE_URL": base_vieja})
    sesion = app.extensions["db"]["fabrica"]()

    assert completar_lecturas(sesion) == 2
    assert completar_lecturas(sesion) == 0
    sesion.close()
    # Migrar otra vez (otro worker de gunicorn) no falla.
    create_app({"TESTING": True, "DATABASE_URL": base_vieja})
    assert app.test_client().get("/api/v2/caracteres/长/").get_json()["lecturas"] == ["zhǎng", "cháng"]


def test_cli_completar_lecturas(monkeypatch, base_vieja, capsys):
    monkeypatch.setenv("DATABASE_URL", base_vieja)

    assert cargar.main(["--completar-lecturas"]) == 0
    assert "Lecturas completadas en 2 caracteres." in capsys.readouterr().out


def test_cli_sin_ruta_ni_completar_es_un_error(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'db.sqlite3'}")

    with pytest.raises(SystemExit):
        cargar.main([])
