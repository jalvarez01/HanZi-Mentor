"""Carga de Make Me a Hanzi con un dataset mínimo (tests/datos/makemeahanzi)."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select

import cargar
from carga import ErrorCarga, base_vacia, cargar as cargar_datos
from modelos import Caracter, Ejercicio, Leccion, Trazo

DATOS = Path(__file__).parent / "datos" / "makemeahanzi"


def caracter(sesion, hanzi):
    return sesion.scalars(select(Caracter).where(Caracter.hanzi == hanzi)).first()


def contar(sesion, modelo):
    return sesion.scalar(select(func.count()).select_from(modelo))


def test_carga_los_niveles_pedidos(sesion):
    resumen = cargar_datos(sesion, DATOS, niveles=[1])

    assert resumen.creados == 2
    assert sorted(c.hanzi for c in sesion.scalars(select(Caracter))) == ["人", "大"]
    # Los demás HSK1 de hsk.py no están en el dataset de prueba.
    assert "一" in resumen.sin_datos


def test_guarda_campos_y_trazos_en_orden(sesion):
    cargar_datos(sesion, DATOS, niveles=[1])

    da = caracter(sesion, "大")
    assert da.pinyin == "dà"
    assert da.definicion.startswith("big")
    assert da.radical == "大"
    assert da.descomposicion == "⿻一人"
    assert da.nivel_hsk == 1
    assert [t.secuencia for t in da.trazos] == [1, 2, 3]
    assert da.trazos[1].mediana == [[500, 800], [450, 500], [200, 150]]


def test_caracter_sin_graficos_queda_sin_trazos(sesion):
    cargar_datos(sesion, DATOS, niveles=[2])

    liang = caracter(sesion, "两")
    assert liang.nivel_hsk == 2
    assert liang.trazos == []


def test_todos_incluye_los_que_no_son_hsk(sesion):
    resumen = cargar_datos(sesion, DATOS, todos=True)

    assert resumen.creados == 4
    assert caracter(sesion, "丶").nivel_hsk is None
    assert resumen.sin_nivel == 1


def test_volver_a_cargar_actualiza_sin_duplicar(sesion):
    cargar_datos(sesion, DATOS, niveles=[1])
    resumen = cargar_datos(sesion, DATOS, niveles=[1])

    assert (resumen.creados, resumen.actualizados) == (0, 2)
    assert contar(sesion, Caracter) == 2
    assert contar(sesion, Trazo) == 5


def test_limpiar_borra_caracteres_y_ejercicios(sesion):
    cargar_datos(sesion, DATOS, todos=True)
    leccion = Leccion(usuario_id=uuid.uuid4(), nivel_hsk=1)
    sesion.add(leccion)
    leccion.generarContenido(sesion, cantidad=2)
    sesion.commit()

    resumen = cargar_datos(sesion, DATOS, niveles=[1], limpiar=True)

    assert resumen.borrados == 4
    assert contar(sesion, Caracter) == 2
    assert contar(sesion, Ejercicio) == 0


def test_falta_un_archivo(sesion, tmp_path):
    with pytest.raises(ErrorCarga, match="dictionary.txt"):
        cargar_datos(sesion, tmp_path, niveles=[1])


def test_nivel_sin_caracteres(sesion):
    with pytest.raises(ErrorCarga, match="niveles"):
        cargar_datos(sesion, DATOS, niveles=[9])


def test_cli_carga_y_respeta_si_vacia(monkeypatch, tmp_path, capsys):
    base = tmp_path / "catalogo.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{base}")

    assert cargar.main(["--ruta", str(DATOS), "--nivel", "1", "2"]) == 0
    assert "3 creados" in capsys.readouterr().out

    assert cargar.main(["--ruta", str(DATOS), "--si-vacia"]) == 0
    assert "ya tiene caracteres" in capsys.readouterr().out


def test_cli_error_devuelve_1(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'db.sqlite3'}")

    assert cargar.main(["--ruta", str(tmp_path)]) == 1
    assert "No se encontró" in capsys.readouterr().err


def test_base_vacia(sesion):
    assert base_vacia(sesion)
    cargar_datos(sesion, DATOS, niveles=[1])
    assert not base_vacia(sesion)
