"""Migración de `ejercicios` sobre una base que ya tiene datos (RF-IA-02).

Las tablas viejas se crean a mano con las columnas que tenían antes de
RF-IA-02, igual que en db_sesiones, y se les cargan filas. La misma
migración se probó sobre una copia real de db_sesiones (ver el reporte de la
fase 2).
"""

import pytest
from sqlalchemy import create_engine, inspect, text

import migraciones
from app import create_app
from fabricas import Dependencias
from tests.conftest import MotorFalso, NotificadorEspia, ProgresoFalso

USUARIO = "12345678123456781234567812345678"

ESQUEMA_VIEJO = (
    """
    CREATE TABLE sesiones (
        id INTEGER NOT NULL PRIMARY KEY,
        usuario_id CHAR(32) NOT NULL,
        nivel_hsk SMALLINT NOT NULL,
        dificultad SMALLINT NOT NULL,
        estado VARCHAR(20) NOT NULL,
        creada_en DATETIME NOT NULL,
        duracion_estimada_min SMALLINT NOT NULL
    )
    """,
    """
    CREATE TABLE ejercicios (
        id INTEGER NOT NULL PRIMARY KEY,
        sesion_id INTEGER NOT NULL REFERENCES sesiones (id) ON DELETE CASCADE,
        caracter VARCHAR(8) NOT NULL,
        tipo VARCHAR(20) NOT NULL,
        dificultad SMALLINT NOT NULL,
        es_refuerzo BOOLEAN NOT NULL,
        respondido BOOLEAN NOT NULL,
        fue_correcto BOOLEAN,
        respondido_en DATETIME
    )
    """,
)

SESIONES = [
    (1, USUARIO, 1, 2, "completada", "2026-11-01 10:00:00.000000", 10),
    (2, USUARIO, 1, 2, "activa", "2026-11-02 10:00:00.000000", 10),
]
EJERCICIOS = [
    (1, 1, "人", "trazo", 2, 1, 1, 0, "2026-11-01 10:05:00.000000"),
    (2, 1, "大", "significado", 2, 0, 1, 1, "2026-11-01 10:06:00.000000"),
    (3, 2, "学", "significado", 2, 0, 0, None, None),
]
COLUMNAS_EJERCICIOS = (
    "id, sesion_id, caracter, tipo, dificultad, es_refuerzo, respondido, fue_correcto, respondido_en"
)


@pytest.fixture
def url_vieja(tmp_path):
    url = f"sqlite:///{(tmp_path / 'vieja.sqlite3').as_posix()}"
    engine = create_engine(url)
    with engine.begin() as conexion:
        for sentencia in ESQUEMA_VIEJO:
            conexion.execute(text(sentencia))
        for fila in SESIONES:
            conexion.execute(text("INSERT INTO sesiones VALUES (:a, :b, :c, :d, :e, :f, :g)"),
                             dict(zip("abcdefg", fila)))
        for fila in EJERCICIOS:
            conexion.execute(text(f"INSERT INTO ejercicios ({COLUMNAS_EJERCICIOS}) VALUES "
                                  "(:a, :b, :c, :d, :e, :f, :g, :h, :i)"), dict(zip("abcdefghi", fila)))
    engine.dispose()
    return url


def filas(engine):
    with engine.connect() as c:
        return (
            [tuple(f) for f in c.execute(text("SELECT * FROM sesiones ORDER BY id"))],
            [tuple(f) for f in c.execute(text(f"SELECT {COLUMNAS_EJERCICIOS} FROM ejercicios ORDER BY id"))],
        )


def columnas(engine, tabla):
    return [c["name"] for c in inspect(engine).get_columns(tabla)]


def crear(url):
    deps = Dependencias(motor=MotorFalso(), notificador=NotificadorEspia(), progreso=ProgresoFalso())
    return create_app({"TESTING": True, "DATABASE_URL": url}, dependencias=deps)


def test_agrega_codigo_error_sin_tocar_los_datos(url_vieja):
    engine = create_engine(url_vieja)
    antes = filas(engine)

    assert migraciones.aplicar(engine) == ["ejercicios.codigo_error"]

    assert columnas(engine, "ejercicios")[-1] == "codigo_error"
    assert filas(engine) == antes == (SESIONES, EJERCICIOS)
    with engine.connect() as c:
        assert c.execute(text("SELECT codigo_error FROM ejercicios")).scalars().all() == [None, None, None]
    engine.dispose()


def test_la_segunda_ejecucion_no_hace_nada(url_vieja):
    engine = create_engine(url_vieja)
    migraciones.aplicar(engine)
    antes = (columnas(engine, "ejercicios"), columnas(engine, "sesiones"), filas(engine))

    assert migraciones.aplicar(engine) == []
    assert migraciones.columnas_faltantes(engine) == []
    assert (columnas(engine, "ejercicios"), columnas(engine, "sesiones"), filas(engine)) == antes
    engine.dispose()


def test_la_tabla_sesiones_no_cambia(url_vieja):
    engine = create_engine(url_vieja)
    antes = columnas(engine, "sesiones")

    migraciones.aplicar(engine)

    assert columnas(engine, "sesiones") == antes
    assert "curva_aplicada_en" not in antes
    engine.dispose()


def test_una_base_nueva_no_necesita_migracion():
    app = crear("sqlite://")

    assert migraciones.aplicar(app.extensions["db"]["engine"]) == []
    assert "codigo_error" in columnas(app.extensions["db"]["engine"], "ejercicios")


def test_sin_las_tablas_no_hace_nada():
    assert migraciones.aplicar(create_engine("sqlite://")) == []


def test_una_imagen_anterior_puede_seguir_insertando(url_vieja):
    engine = create_engine(url_vieja)
    migraciones.aplicar(engine)

    with engine.begin() as c:
        c.execute(text(f"INSERT INTO ejercicios ({COLUMNAS_EJERCICIOS}) VALUES "
                       "(4, 2, '校', 'trazo', 2, 1, 0, NULL, NULL)"))
        assert c.execute(text("SELECT codigo_error FROM ejercicios WHERE id = 4")).scalar() is None
    engine.dispose()


def test_el_servicio_arranca_sobre_la_base_vieja_y_responde(url_vieja):
    app = crear(url_vieja)
    client = app.test_client()

    detalle = client.get("/api/v2/sesiones/2/").get_json()
    assert [e["caracter"] for e in detalle["ejercicios"]] == ["学"]

    resp = client.post("/api/v2/ejercicios/3/responder/", json={"acerto": False, "codigo_error": "NO_SABE"})
    assert resp.status_code == 200
    with app.extensions["db"]["engine"].connect() as c:
        assert c.execute(text("SELECT codigo_error FROM ejercicios WHERE id = 3")).scalar() == "NO_SABE"
    app.extensions["db"]["engine"].dispose()


def test_el_esquema_migrado_es_igual_al_de_una_base_nueva(url_vieja):
    migrada = create_engine(url_vieja)
    migraciones.aplicar(migrada)
    nueva = crear("sqlite://").extensions["db"]["engine"]

    def codigo_error(engine):
        (columna,) = [c for c in inspect(engine).get_columns("ejercicios") if c["name"] == "codigo_error"]
        return (columna["nullable"], columna["default"], str(columna["type"]))

    assert codigo_error(migrada) == codigo_error(nueva) == (True, None, "VARCHAR(40)")
    migrada.dispose()
