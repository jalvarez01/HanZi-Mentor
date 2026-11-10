"""detectar_patron_error (RF-IA-01): función pura, sin base ni Flask.

Cada prueba arma el historial a mano, con la misma forma que guarda
ProgresoUsuario.historial_errores.
"""

from datetime import datetime, timedelta, timezone

import pytest

from dominio.patrones import (
    MIN_OCURRENCIAS,
    PATRONES_DE_ERROR,
    PROPORCION_MINIMA,
    VENTANA_DIAS,
    detectar_patron_error,
)

AHORA = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


def fallo(codigo, caracter="学", hace_dias=1.0, origen="sesion", dominado=False):
    return {
        "codigo": codigo,
        "caracter": caracter,
        "fecha": (AHORA - timedelta(days=hace_dias)).isoformat(),
        "origen": origen,
        "dominado": dominado,
    }


def varios(codigo, cantidad, origen="trazos", caracteres="人大水火山口日月中小"):
    """`cantidad` fallos del mismo código, cada uno en un carácter distinto."""
    return [fallo(codigo, caracteres[i % len(caracteres)], origen=origen) for i in range(cantidad)]


def codigos(historial, **opciones):
    return [p.codigo for p in detectar_patron_error(historial, AHORA, **opciones)]


def test_los_umbrales_son_los_aprobados():
    assert (VENTANA_DIAS, MIN_OCURRENCIAS, PROPORCION_MINIMA) == (14, 3, 0.30)


# ---------- pocos datos ----------


@pytest.mark.parametrize("historial", [None, [], [fallo("TRAZO_INVERTIDO")], varios("TRAZO_INVERTIDO", 2)])
def test_sin_datos_o_con_uno_o_dos_fallos_no_hay_patron(historial):
    assert detectar_patron_error(historial, AHORA) == []


def test_dos_fallos_de_cada_tipo_no_alcanzan():
    historial = (
        varios("TRAZO_INVERTIDO", 2) + varios("PINYIN_INICIAL", 2) + varios("NO_SABE", 2)
        + varios("SIGNIFICADO_PARCIAL", 2)
    )

    assert codigos(historial) == []


# ---------- patrones por tipo de error ----------

CASOS_POR_CODIGO = [
    ("TRAZO_INVERTIDO", "PATRON_TRAZO_INVERTIDO"),
    ("TRAZO_CORTO", "PATRON_TRAZO_LONGITUD"),
    ("TRAZO_LARGO", "PATRON_TRAZO_LONGITUD"),
    ("TRAZO_INCOMPLETO", "PATRON_TRAZO_LONGITUD"),
    ("TRAZO_FUERA_DE_LUGAR", "PATRON_TRAZO_POSICION"),
    ("TRAZO_IMPRECISO", "PATRON_TRAZO_FORMA"),
    ("PINYIN_INICIAL", "PATRON_PINYIN_INICIAL"),
    ("PINYIN_FINAL", "PATRON_PINYIN_FINAL"),
    ("PINYIN_DISTINTO", "PATRON_PINYIN_LECTURA"),
    ("NO_SABE", "PATRON_NO_SABE"),
    ("SIGNIFICADO_PARCIAL", "PATRON_SIGNIFICADO"),
    ("SIGNIFICADO_CERCANO", "PATRON_SIGNIFICADO"),
    ("SIGNIFICADO_DISTINTO", "PATRON_SIGNIFICADO"),
]


@pytest.mark.parametrize("codigo, patron", CASOS_POR_CODIGO)
def test_tres_fallos_del_mismo_tipo_son_un_patron_y_dos_no(codigo, patron):
    assert codigos(varios(codigo, 3)) == [patron]
    assert codigos(varios(codigo, 2)) == []


def test_cada_codigo_de_evaluacion_alimenta_un_solo_patron():
    from dominio.codigos import CODIGOS_EVALUACION, NO_SABE

    alimentados = [
        codigo
        for definiciones in PATRONES_DE_ERROR.values()
        for codigos_del_patron, _, _ in definiciones.values()
        for codigo in codigos_del_patron
    ]
    assert sorted(alimentados) == sorted(CODIGOS_EVALUACION + (NO_SABE,))


def test_los_codigos_de_longitud_se_suman_en_un_patron():
    historial = [fallo("TRAZO_CORTO", "人"), fallo("TRAZO_LARGO", "大"), fallo("TRAZO_INCOMPLETO", "水")]

    (patron,) = detectar_patron_error(historial, AHORA)

    assert (patron.codigo, patron.tipo, patron.frecuencia) == ("PATRON_TRAZO_LONGITUD", "error", 3)


def test_la_proporcion_se_mide_sobre_la_familia():
    # 3 de 10 fallos de trazo (30 %): patrón. 3 de 11 (27 %): no.
    justo = varios("TRAZO_INVERTIDO", 3) + varios("TRAZO_IMPRECISO", 7)
    debajo = varios("TRAZO_INVERTIDO", 3) + varios("TRAZO_IMPRECISO", 8)

    assert "PATRON_TRAZO_INVERTIDO" in codigos(justo)
    assert "PATRON_TRAZO_INVERTIDO" not in codigos(debajo)
    assert "PATRON_TRAZO_FORMA" in codigos(debajo)


def test_los_fallos_de_otra_familia_no_diluyen_el_patron():
    # 3 de pinyin entre 40 de trazo: sigue siendo el 100 % de su familia.
    historial = varios("PINYIN_INICIAL", 3) + varios("TRAZO_IMPRECISO", 40)

    assert "PATRON_PINYIN_INICIAL" in codigos(historial)


def test_autocalificado_y_sin_codigo_no_cuentan_en_ninguna_familia():
    # Ni dan patrón de tipo ni entran al denominador de trazo.
    historial = (
        varios("TRAZO_INVERTIDO", 3)
        + varios("TRAZO_AUTOCALIFICADO", 20, origen="trazos")
        + varios(None, 20, origen="trazos")
    )

    assert codigos(historial) == ["PATRON_TRAZO_INVERTIDO"]


def test_los_fallos_de_sesion_y_de_trazos_cuentan_para_el_tipo_de_error():
    historial = [
        fallo("PINYIN_FINAL", "学", origen="sesion"),
        fallo("PINYIN_FINAL", "校", origen="sesion"),
        fallo("PINYIN_FINAL", "老", origen="trazos"),
    ]

    assert codigos(historial) == ["PATRON_PINYIN_FINAL"]


# ---------- ventana de tiempo ----------


def test_los_fallos_fuera_de_la_ventana_no_cuentan():
    viejos = [fallo("TRAZO_INVERTIDO", c, hace_dias=15) for c in "人大水"]
    assert codigos(viejos) == []

    # Dos dentro y uno fuera: tampoco.
    mezcla = [fallo("TRAZO_INVERTIDO", "人", 15), fallo("TRAZO_INVERTIDO", "大", 2), fallo("TRAZO_INVERTIDO", "水", 1)]
    assert codigos(mezcla) == []


def test_el_borde_de_la_ventana_entra():
    en_el_borde = [fallo("TRAZO_INVERTIDO", c, hace_dias=14) for c in "人大水"]
    un_segundo_antes = [fallo("TRAZO_INVERTIDO", c, hace_dias=14 + 1 / 86400) for c in "人大水"]

    assert codigos(en_el_borde) == ["PATRON_TRAZO_INVERTIDO"]
    assert codigos(un_segundo_antes) == []


def test_la_ventana_se_puede_cambiar():
    historial = [fallo("TRAZO_INVERTIDO", c, hace_dias=5) for c in "人大水"]

    assert codigos(historial, ventana_dias=3) == []
    assert codigos(historial, ventana_dias=7) == ["PATRON_TRAZO_INVERTIDO"]


def test_fechas_sin_zona_o_con_z_se_leen_como_utc():
    historial = varios("TRAZO_INVERTIDO", 3)
    historial[0]["fecha"] = "2026-11-08T12:00:00"
    historial[1]["fecha"] = "2026-11-08T12:00:00+00:00"
    historial[2]["fecha"] = "2026-11-08T07:00:00-05:00"

    (patron,) = detectar_patron_error(historial, AHORA)

    assert patron.ultima_vez == datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


# ---------- patrones por carácter ----------


def test_el_mismo_caracter_fallado_tres_veces_en_sesion_es_recurrente():
    historial = [fallo("TRAZO_AUTOCALIFICADO", "学", d) for d in (3, 2, 1)]

    (patron,) = detectar_patron_error(historial, AHORA)

    assert (patron.codigo, patron.tipo, patron.frecuencia) == ("PATRON_CARACTER_RECURRENTE", "caracter", 3)
    assert patron.caracteres == ("学",)
    assert patron.ultima_vez == AHORA - timedelta(days=1)


def test_recurrente_cuenta_fallos_con_cualquier_codigo_o_sin_el():
    historial = [fallo(None, "学"), fallo("NO_SABE", "学"), fallo("PINYIN_FINAL", "学")]

    assert codigos(historial) == ["PATRON_CARACTER_RECURRENTE"]


def test_recurrente_no_cuenta_los_fallos_de_trazos():
    historial = [fallo("TRAZO_AUTOCALIFICADO", "学", origen="sesion")] * 2 + [
        fallo("TRAZO_FUERA_DE_LUGAR", "学", origen="trazos"),
        fallo("TRAZO_IMPRECISO", "学", origen="trazos"),
    ]

    assert "PATRON_CARACTER_RECURRENTE" not in codigos(historial)


def test_recurrente_junta_los_caracteres_del_mas_fallado_al_menos():
    historial = (
        [fallo(None, "校")] * 3 + [fallo(None, "学")] * 5 + [fallo(None, "老")] * 2
    )

    (patron,) = detectar_patron_error(historial, AHORA)

    # 老 tiene dos fallos: no entra ni en la lista ni en la frecuencia.
    assert patron.caracteres == ("学", "校")
    assert patron.frecuencia == 8


def test_retroceso_con_tres_fallos_de_caracteres_dominados():
    dos = [fallo(None, "学", dominado=True), fallo(None, "校", dominado=True)]
    tres = dos + [fallo(None, "老", dominado=True)]

    assert codigos(dos) == []
    (patron,) = detectar_patron_error(tres, AHORA)
    assert (patron.codigo, patron.tipo, patron.frecuencia) == ("PATRON_RETROCESO", "caracter", 3)
    assert sorted(patron.caracteres) == sorted(("学", "校", "老"))


def test_retroceso_no_cuenta_fallos_sin_dominar_ni_los_de_trazos():
    historial = [
        fallo(None, "学", dominado=True),
        fallo(None, "校", dominado=True),
        fallo(None, "老", dominado=False),
        fallo("TRAZO_CORTO", "人", origen="trazos", dominado=True),
    ]

    assert "PATRON_RETROCESO" not in codigos(historial)


# ---------- salida ----------


def test_orden_por_frecuencia_despues_por_reciente_y_por_codigo():
    historial = (
        [fallo("PINYIN_INICIAL", c, hace_dias=5) for c in "人大水火"]      # 4, pinyin
        + [fallo("TRAZO_INVERTIDO", c, hace_dias=1, origen="trazos") for c in "山口日"]  # 3, reciente
        + [fallo("SIGNIFICADO_PARCIAL", c, hace_dias=3) for c in "月中小"]  # 3, anterior
    )

    assert codigos(historial) == ["PATRON_PINYIN_INICIAL", "PATRON_TRAZO_INVERTIDO", "PATRON_SIGNIFICADO"]

    empate = [fallo("TRAZO_INVERTIDO", c, hace_dias=1) for c in "人大水"] + [
        fallo("PINYIN_FINAL", c, hace_dias=1) for c in "火山口"
    ]
    assert codigos(empate) == ["PATRON_PINYIN_FINAL", "PATRON_TRAZO_INVERTIDO"]


def test_la_misma_entrada_da_siempre_la_misma_salida():
    historial = varios("TRAZO_INVERTIDO", 6) + [fallo(None, "学")] * 4

    assert detectar_patron_error(historial, AHORA) == detectar_patron_error(list(historial), AHORA)


def test_como_maximo_cinco_caracteres_del_mas_fallado_al_menos():
    historial = (
        [fallo("TRAZO_INVERTIDO", "人", origen="trazos")] * 3
        + [fallo("TRAZO_INVERTIDO", "大", origen="trazos")] * 2
        + [fallo("TRAZO_INVERTIDO", c, hace_dias=2, origen="trazos") for c in "水火山口日"]
    )

    (patron,) = detectar_patron_error(historial, AHORA)

    assert patron.frecuencia == 10
    assert len(patron.caracteres) == 5
    assert patron.caracteres[:2] == ("人", "大")


def test_cada_patron_tiene_titulo_y_consejo():
    historial = varios("PINYIN_FINAL", 3)

    (patron,) = detectar_patron_error(historial, AHORA)

    assert patron.titulo == "Terminación del pinyin"
    assert patron.consejo == "Decí la sílaba en voz alta y prestá atención a cómo termina."


def test_las_entradas_mal_formadas_se_ignoran():
    basura = [
        None, "texto", 7, {}, {"codigo": "TRAZO_INVERTIDO"},
        {"codigo": "TRAZO_INVERTIDO", "caracter": "人"},
        {"codigo": "TRAZO_INVERTIDO", "caracter": "人", "fecha": "ayer"},
        {"codigo": "TRAZO_INVERTIDO", "caracter": "", "fecha": AHORA.isoformat()},
        {"codigo": "TRAZO_INVERTIDO", "caracter": 5, "fecha": AHORA.isoformat()},
        {"codigo": ["TRAZO_INVERTIDO"], "caracter": "人", "fecha": AHORA.isoformat(), "origen": "trazos"},
    ]

    assert detectar_patron_error(basura, AHORA) == []
    assert codigos(basura + varios("TRAZO_INVERTIDO", 3)) == ["PATRON_TRAZO_INVERTIDO"]


def test_una_entrada_sin_origen_ni_dominado_es_de_sesion_y_no_dominada():
    historial = [{"codigo": None, "caracter": "学", "fecha": AHORA.isoformat()}] * 3

    assert codigos(historial) == ["PATRON_CARACTER_RECURRENTE"]
