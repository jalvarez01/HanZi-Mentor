"""Migración de `progresos` sobre una base que ya tiene datos (RF-IA-01).

La tabla vieja se crea a mano con las 11 columnas que tenía antes de
RF-IA-01, igual que la de db_progreso en Docker, y se le cargan filas. La
misma migración se probó sobre una copia real de db_progreso (ver README).
"""

import json

import pytest
from sqlalchemy import create_engine, inspect, text

import migraciones
from app import create_app

USUARIO_A = "12345678123456781234567812345678"
USUARIO_B = "87654321432187654321876543218765"

ESQUEMA_VIEJO = """
CREATE TABLE progresos (
    id INTEGER NOT NULL PRIMARY KEY,
    usuario_id CHAR(32) NOT NULL UNIQUE,
    nivel_hsk SMALLINT NOT NULL,
    nivel_max_desbloqueado SMALLINT NOT NULL,
    tasa_acierto FLOAT NOT NULL,
    caracteres_dominados JSON NOT NULL,
    errores_frecuentes JSON NOT NULL,
    aciertos_consecutivos JSON NOT NULL,
    agenda_repaso JSON NOT NULL,
    proximo_repaso DATETIME,
    actualizado_en DATETIME NOT NULL
)
"""

FILAS = [
    (1, USUARIO_A, 2, 3, 0.7321, '["人", "大"]', '{"学": 2}', '{"人": 3, "学": 0}',
     '{"人": "2026-11-12T10:00:00+00:00"}', "2026-11-10 22:00:00.000000", "2026-11-09 10:00:00.000000"),
    (2, USUARIO_B, 1, 1, 0.5, "[]", "{}", "{}", "{}", None, "2026-11-01 08:30:00.000000"),
]

COLUMNAS_VIEJAS = (
    "id, usuario_id, nivel_hsk, nivel_max_desbloqueado, tasa_acierto, caracteres_dominados, "
    "errores_frecuentes, aciertos_consecutivos, agenda_repaso, proximo_repaso, actualizado_en"
)


@pytest.fixture
def url_vieja(tmp_path):
    """Una base SQLite en archivo con el esquema anterior y dos filas."""
    url = f"sqlite:///{(tmp_path / 'vieja.sqlite3').as_posix()}"
    engine = create_engine(url)
    with engine.begin() as conexion:
        conexion.execute(text(ESQUEMA_VIEJO))
        for fila in FILAS:
            conexion.execute(
                text(f"INSERT INTO progresos ({COLUMNAS_VIEJAS}) VALUES "
                     "(:a, :b, :c, :d, :e, :f, :g, :h, :i, :j, :k)"),
                dict(zip("abcdefghijk", fila)),
            )
    engine.dispose()
    return url


def filas_viejas(engine):
    with engine.connect() as conexion:
        return [tuple(f) for f in conexion.execute(text(f"SELECT {COLUMNAS_VIEJAS} FROM progresos ORDER BY id"))]


def columnas(engine):
    return [c["name"] for c in inspect(engine).get_columns("progresos")]


def test_agrega_las_columnas_sin_tocar_los_datos(url_vieja):
    engine = create_engine(url_vieja)
    antes = filas_viejas(engine)
    assert "historial_errores" not in columnas(engine)

    agregadas = migraciones.aplicar(engine)

    assert agregadas == ["errores_por_codigo", "historial_errores", "curva_olvido"]
    assert columnas(engine)[-3:] == ["errores_por_codigo", "historial_errores", "curva_olvido"]
    assert filas_viejas(engine) == antes == FILAS
    with engine.connect() as conexion:
        nuevas = conexion.execute(
            text("SELECT errores_por_codigo, historial_errores, curva_olvido FROM progresos ORDER BY id")
        ).all()
    # Las filas que ya existían toman el valor por defecto.
    assert [tuple(json.loads(v) for v in fila) for fila in nuevas] == [({}, [], {}), ({}, [], {})]
    engine.dispose()


def test_la_segunda_ejecucion_no_hace_nada(url_vieja):
    engine = create_engine(url_vieja)
    migraciones.aplicar(engine)
    antes = (columnas(engine), filas_viejas(engine))

    assert migraciones.aplicar(engine) == []
    assert migraciones.columnas_faltantes(engine) == []
    assert (columnas(engine), filas_viejas(engine)) == antes
    engine.dispose()


def test_una_base_nueva_no_necesita_migracion():
    app = create_app({"TESTING": True, "DATABASE_URL": "sqlite://"})
    engine = app.extensions["db"]["engine"]

    assert migraciones.aplicar(engine) == []
    assert columnas(engine)[-2:] != [] and "historial_errores" in columnas(engine)


def test_sin_la_tabla_no_hace_nada():
    engine = create_engine("sqlite://")

    assert migraciones.aplicar(engine) == []


def test_el_valor_por_defecto_queda_en_la_base(url_vieja):
    """Una imagen anterior, que no conoce las columnas, puede seguir insertando."""
    engine = create_engine(url_vieja)
    migraciones.aplicar(engine)

    with engine.begin() as conexion:
        conexion.execute(
            text(f"INSERT INTO progresos ({COLUMNAS_VIEJAS}) VALUES "
                 "(3, 'abcdefabcdefabcdefabcdefabcdefab', 1, 1, 0.5, '[]', '{}', '{}', '{}', NULL, "
                 "'2026-11-09 10:00:00.000000')")
        )
        fila = conexion.execute(
            text("SELECT errores_por_codigo, historial_errores FROM progresos WHERE id = 3")
        ).one()
    assert (json.loads(fila[0]), json.loads(fila[1])) == ({}, [])
    engine.dispose()


def test_el_servicio_arranca_sobre_la_base_vieja_y_conserva_el_progreso(url_vieja):
    app = create_app({"TESTING": True, "DATABASE_URL": url_vieja})
    client = app.test_client()
    usuario = "12345678-1234-5678-1234-567812345678"

    datos = client.get(f"/api/v2/progreso/{usuario}/").get_json()

    assert datos["tasa_acierto"] == 0.7321
    assert datos["caracteres_dominados"] == ["人", "大"]
    assert datos["errores_frecuentes"] == {"学": 2}
    assert datos["aciertos_consecutivos"] == {"人": 3, "学": 0}
    # RF-IA-02: la fecha más cercana de la agenda. La columna de esta fila
    # tiene una fecha anterior que no está en la agenda (el defecto que se
    # corrigió); la agenda no se toca.
    assert datos["proximo_repaso"] == "2026-11-12T10:00:00Z"
    assert client.get(f"/api/v2/progreso/{usuario}/patrones/").get_json()["patrones"] == []

    # Y se puede seguir escribiendo sobre la fila migrada.
    resp = client.post(
        f"/api/v2/progreso/{usuario}/respuestas/",
        json={"caracter": "学", "acerto": False, "codigo_error": "PINYIN_FINAL"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["errores_frecuentes"] == {"学": 3}
    assert resp.get_json()["caracteres_dominados"] == ["人", "大"]
    app.extensions["db"]["engine"].dispose()


def test_el_esquema_migrado_es_igual_al_de_una_base_nueva(url_vieja):
    migrada = create_engine(url_vieja)
    migraciones.aplicar(migrada)
    nueva = create_app({"TESTING": True, "DATABASE_URL": "sqlite://"}).extensions["db"]["engine"]

    def resumen(engine):
        return {
            c["name"]: (c["nullable"], str(c["default"]))
            for c in inspect(engine).get_columns("progresos")
            if c["name"] in ("errores_por_codigo", "historial_errores", "curva_olvido")
        }

    assert resumen(migrada) == resumen(nueva) == {
        "errores_por_codigo": (False, "'{}'"),
        "historial_errores": (False, "'[]'"),
        "curva_olvido": (False, "'{}'"),
    }
    migrada.dispose()



def test_desde_la_version_de_rf_ia_01_solo_agrega_curva_olvido(url_vieja):
    """La base real ya tiene las columnas de RF-IA-01: solo falta curva_olvido."""
    engine = create_engine(url_vieja)
    with engine.begin() as conexion:
        conexion.execute(text("ALTER TABLE progresos ADD COLUMN errores_por_codigo JSON NOT NULL DEFAULT '{}'"))
        conexion.execute(text("ALTER TABLE progresos ADD COLUMN historial_errores JSON NOT NULL DEFAULT '[]'"))

    assert migraciones.aplicar(engine) == ["curva_olvido"]
    assert filas_viejas(engine) == FILAS
    engine.dispose()


def test_create_app_crea_la_tabla_sesiones_aplicadas_en_una_base_vieja(url_vieja):
    app = create_app({"TESTING": True, "DATABASE_URL": url_vieja})
    engine = app.extensions["db"]["engine"]

    assert inspect(engine).has_table("sesiones_aplicadas")
    assert [c["name"] for c in inspect(engine).get_columns("sesiones_aplicadas")] == [
        "usuario_id", "sesion_id", "aplicada_en",
    ]
    assert filas_viejas(engine) == FILAS
    engine.dispose()


def test_la_curva_sobre_la_base_vieja_conserva_las_fechas_de_los_demas(url_vieja):
    """Inicialización perezosa: el carácter con agenda anterior parte de su
    racha, y los demás caracteres conservan su fecha."""
    app = create_app({"TESTING": True, "DATABASE_URL": url_vieja})
    client = app.test_client()
    usuario = "12345678-1234-5678-1234-567812345678"
    url = f"/api/v2/progreso/{usuario}/"

    # 人 tenía racha 3 y fecha 2026-11-12T10:00 con el algoritmo anterior.
    client.post(f"{url}respuestas/", json={"caracter": "学", "acerto": True})
    resp = client.post(f"{url}curva-olvido/", json={
        "sesion_id": 1, "cerrada_en": "2026-11-13T09:00:00+00:00",
        "respuestas": [{"caracter": "学", "acerto": True}],
    })

    assert resp.get_json()["repasos"] == [{
        "caracter": "学", "proximo_repaso": "2026-11-14T09:00:00Z", "intervalo_dias": 1, "repeticiones": 1,
    }]
    repasos = client.get(f"{url}repasos/?dias=30", headers={}).get_json()
    fechas = {r["caracter"]: r for r in repasos["vencidos"] + repasos["proximos"]}
    # 人 conserva su fecha y su estado sale de la racha 3: intervalo 7.
    assert fechas["人"]["proximo_repaso"] == "2026-11-12T10:00:00Z"
    assert (fechas["人"]["repeticiones"], fechas["人"]["intervalo_dias"]) == (3, 7)
    app.extensions["db"]["engine"].dispose()
