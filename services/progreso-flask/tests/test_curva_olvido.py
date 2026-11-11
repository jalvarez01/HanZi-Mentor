"""Curva de olvido (RF-IA-02): SM-2 contra valores calculados a mano.

Fórmula de la facilidad: f + 0.1 - (5 - q) x (0.08 + (5 - q) x 0.02).
  q=5: +0.10   q=4: 0   q=3: -0.14   q=2: -0.32   q=1: -0.54   q=0: -0.80
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest

from dominio import progreso as reglas
from dominio.curva_olvido import (
    EstadoCurva,
    actualizar_curva_olvido,
    calidad_de_respuesta,
    estado_desde_racha,
    nueva_facilidad,
    peor_calidad_por_caracter,
)

CIERRE = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


@dataclass
class Progreso:
    """Doble de la entidad con los campos que usa la curva."""

    aciertos_consecutivos: dict = field(default_factory=dict)
    agenda_repaso: dict = field(default_factory=dict)
    curva_olvido: dict = field(default_factory=dict)
    proximo_repaso: datetime | None = None


def respuesta(caracter, acerto, codigo_error=None):
    return {"caracter": caracter, "acerto": acerto, "codigo_error": codigo_error}


# ---------- facilidad ----------


@pytest.mark.parametrize("calidad, esperada", [
    (5, 2.6), (4, 2.5), (3, 2.36), (2, 2.18), (1, 1.96), (0, 1.7),
])
def test_facilidad_desde_2_5_segun_la_calidad(calidad, esperada):
    assert nueva_facilidad(2.5, calidad) == esperada


def test_la_facilidad_nunca_baja_de_1_3():
    assert nueva_facilidad(1.5, 0) == 1.3
    assert nueva_facilidad(1.3, 1) == 1.3


# ---------- intervalos (tabla de la Fase 0) ----------


def test_tabla_calculada_a_mano():
    """Carácter nuevo; cada fila es una sesión cerrada a las 12:00."""
    estado = None
    filas = []
    momento = CIERRE
    for calidad in (4, 4, 4, 2, 4):
        estado, cuando = actualizar_curva_olvido(estado, calidad, momento)
        filas.append((calidad, estado.facilidad, estado.repeticiones, estado.intervalo_dias, cuando - momento))
        momento = cuando

    assert filas == [
        (4, 2.5, 1, 1, timedelta(days=1)),
        (4, 2.5, 2, 6, timedelta(days=6)),
        (4, 2.5, 3, 15, timedelta(days=15)),     # round(6 x 2.5)
        (2, 2.18, 0, 0, timedelta(hours=12)),   # fallo: 12 horas
        (4, 2.18, 1, 1, timedelta(days=1)),     # vuelve a empezar
    ]


def test_la_tercera_repeticion_usa_la_facilidad_anterior():
    # Facilidad 2.18 y 6 días: round(6 x 2.18) = round(13.08) = 13. Con q=5
    # la facilidad sube a 2.28 después, pero el intervalo usa 2.18.
    estado, cuando = actualizar_curva_olvido(EstadoCurva(2.18, 2, 6), 5, CIERRE)

    assert (estado.intervalo_dias, estado.facilidad, estado.repeticiones) == (13, 2.28, 3)
    assert cuando == CIERRE + timedelta(days=13)


def test_el_intervalo_redondea_la_mitad_hacia_arriba():
    # 7 x 2.5 = 17.5 da 18 (round() de Python daría 18 también, por par).
    assert actualizar_curva_olvido(EstadoCurva(2.5, 3, 7), 4, CIERRE)[0].intervalo_dias == 18
    # 5 x 2.5 = 12.5: la mitad hacia arriba da 13 (round() daría 12).
    assert actualizar_curva_olvido(EstadoCurva(2.5, 3, 5), 4, CIERRE)[0].intervalo_dias == 13


def test_calidad_3_cuenta_como_acierto_y_baja_la_facilidad():
    estado, cuando = actualizar_curva_olvido(EstadoCurva(2.5, 2, 6), 3, CIERRE)

    assert (estado.facilidad, estado.repeticiones, estado.intervalo_dias) == (2.36, 3, 15)
    assert cuando == CIERRE + timedelta(days=15)


@pytest.mark.parametrize("calidad, facilidad", [(2, 2.18), (1, 1.96), (0, 1.7)])
def test_un_fallo_reinicia_y_agenda_a_las_12_horas(calidad, facilidad):
    estado, cuando = actualizar_curva_olvido(EstadoCurva(2.5, 4, 40), calidad, CIERRE)

    assert estado == EstadoCurva(facilidad, 0, 0)
    assert cuando == CIERRE + timedelta(hours=12)


@pytest.mark.parametrize("calidad", [-1, 6])
def test_calidad_fuera_de_rango(calidad):
    with pytest.raises(ValueError):
        actualizar_curva_olvido(EstadoCurva(), calidad, CIERRE)


# ---------- respuesta a calidad ----------


@pytest.mark.parametrize("acerto, codigo, calidad", [
    (True, None, 4),
    (True, "NO_SABE", 4),               # con acierto, el código no cuenta
    (False, "PINYIN_INICIAL", 2),
    (False, "PINYIN_FINAL", 2),
    (False, "SIGNIFICADO_PARCIAL", 2),
    (False, "SIGNIFICADO_CERCANO", 2),
    (False, "PINYIN_DISTINTO", 1),
    (False, "SIGNIFICADO_DISTINTO", 1),
    (False, "TRAZO_AUTOCALIFICADO", 1),
    (False, None, 1),
    (False, "TRAZO_INVERTIDO", 1),      # no llega a una sesión: fallo sin código
    (False, "NO_SABE", 0),
])
def test_calidad_de_cada_respuesta(acerto, codigo, calidad):
    assert calidad_de_respuesta(acerto, codigo) == calidad


def test_peor_calidad_por_caracter_en_el_orden_de_la_sesion():
    respuestas = [
        respuesta("学", True),
        respuesta("校", False, "PINYIN_FINAL"),
        respuesta("学", False, "NO_SABE"),
        respuesta("校", True),
        respuesta("人", True),
    ]

    assert peor_calidad_por_caracter(respuestas) == {"学": 0, "校": 2, "人": 4}
    assert list(peor_calidad_por_caracter(respuestas)) == ["学", "校", "人"]


# ---------- inicialización desde el algoritmo anterior ----------


@pytest.mark.parametrize("racha, repeticiones, intervalo", [
    (0, 0, 0), (1, 1, 1), (2, 2, 3), (3, 3, 7), (6, 6, 90), (9, 9, 90),
])
def test_estado_desde_la_racha_anterior(racha, repeticiones, intervalo):
    assert estado_desde_racha(racha) == EstadoCurva(2.5, repeticiones, intervalo)


def test_estado_guardado_con_datos_malos_no_se_usa():
    assert EstadoCurva.desde_dict({"facilidad": "x", "repeticiones": 1, "intervalo_dias": 1}) is None
    assert EstadoCurva.desde_dict({"facilidad": 2.0}) is None
    assert EstadoCurva.desde_dict(None) is None
    assert EstadoCurva.desde_dict({"facilidad": 0.5, "repeticiones": -2, "intervalo_dias": 3}) == EstadoCurva(1.3, 0, 3)


def test_guardar_estado_previo_solo_para_caracteres_con_agenda_anterior():
    progreso = Progreso(
        aciertos_consecutivos={"人": 3, "学": 1},
        agenda_repaso={"人": "2026-11-12T10:00:00+00:00"},
    )

    reglas.guardar_estado_previo(progreso, "人")   # agenda anterior: se fija
    reglas.guardar_estado_previo(progreso, "学")   # sin agenda: carácter nuevo

    assert progreso.curva_olvido == {"人": {"facilidad": 2.5, "repeticiones": 3, "intervalo_dias": 7}}
    # Ya fijado: una racha nueva no lo cambia.
    progreso.aciertos_consecutivos["人"] = 4
    reglas.guardar_estado_previo(progreso, "人")
    assert progreso.curva_olvido["人"]["repeticiones"] == 3
    assert progreso.agenda_repaso == {"人": "2026-11-12T10:00:00+00:00"}


# ---------- aplicar una sesión ----------


def test_aplicar_curva_actualiza_cada_caracter_una_vez_con_su_peor_respuesta():
    progreso = Progreso(
        curva_olvido={"人": {"facilidad": 2.5, "repeticiones": 2, "intervalo_dias": 6}},
        agenda_repaso={"人": "2026-11-04T12:00:00+00:00", "大": "2026-12-01T00:00:00+00:00"},
    )

    resultado = reglas.aplicar_curva_olvido(progreso, [
        respuesta("人", True),
        respuesta("学", True),
        respuesta("人", True),
        respuesta("校", False, "NO_SABE"),
    ], CIERRE)

    assert [(r["caracter"], r["intervalo_dias"], r["repeticiones"]) for r in resultado] == [
        ("人", 15, 3), ("学", 1, 1), ("校", 0, 0),
    ]
    assert progreso.agenda_repaso == {
        "人": "2026-11-25T12:00:00+00:00",
        "大": "2026-12-01T00:00:00+00:00",   # no se respondió: no cambia
        "学": "2026-11-11T12:00:00+00:00",
        "校": "2026-11-11T00:00:00+00:00",
    }
    assert progreso.curva_olvido["校"] == {"facilidad": 1.7, "repeticiones": 0, "intervalo_dias": 0}
    assert progreso.proximo_repaso == CIERRE + timedelta(hours=12)


def test_un_caracter_con_agenda_anterior_sin_estado_parte_de_su_racha():
    """Si no se fijó antes (sesión empezada antes del cambio), se usa la racha
    actual. Racha 2 -> intervalo 3; un acierto da round(3 x 2.5) = 8."""
    progreso = Progreso(aciertos_consecutivos={"人": 2}, agenda_repaso={"人": "2026-11-01T00:00:00+00:00"})

    (fila,) = reglas.aplicar_curva_olvido(progreso, [respuesta("人", True)], CIERRE)

    assert (fila["repeticiones"], fila["intervalo_dias"]) == (3, 8)
    assert fila["proximo_repaso"] == CIERRE + timedelta(days=8)


# ---------- listar repasos ----------


def test_listar_repasos_separa_vencidos_y_proximos_y_ordena():
    progreso = Progreso(agenda_repaso={
        "人": (CIERRE - timedelta(days=1)).isoformat(),
        "大": (CIERRE - timedelta(days=3)).isoformat(),
        "学": (CIERRE + timedelta(days=2)).isoformat(),
        "校": (CIERRE + timedelta(hours=5)).isoformat(),
        "老": (CIERRE + timedelta(days=8)).isoformat(),   # fuera de 7 días
        "师": CIERRE.isoformat(),                          # justo ahora: vencido
        "坏": "no es fecha",
    })

    vencidos, proximos = reglas.listar_repasos(progreso, CIERRE, dias=7, limite=20)

    assert [r["caracter"] for r in vencidos] == ["大", "人", "师"]
    assert [r["caracter"] for r in proximos] == ["校", "学"]
    assert reglas.listar_repasos(progreso, CIERRE, dias=7, limite=1) == (vencidos[:1], proximos[:1])
    _, con_8_dias = reglas.listar_repasos(progreso, CIERRE, dias=8, limite=20)
    assert [r["caracter"] for r in con_8_dias] == ["校", "学", "老"]
