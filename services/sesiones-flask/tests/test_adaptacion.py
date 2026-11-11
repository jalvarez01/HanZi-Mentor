"""Ejercicios adaptativos (RF-IA-03): si progreso-flask detecta un patrón de
error, el tutor ejecuta generarEjercicioAdaptado(p) y la sesión incluye
ejercicios dirigidos a esa debilidad."""

import pytest

from clientes import ProgresoRemoto
from dominio.adaptacion import (
    TIPO_POR_PATRON,
    EjercicioAdaptado,
    adaptar_a_patrones,
    dificultad_adaptada,
    generar_ejercicio_adaptado,
)
from motores import MotorTutorMock
from servicio import SesionEstudioService
from tests.conftest import USUARIO, MotorFalso, ProgresoFalso
from tests.test_clientes import TransporteFalso, cliente

INVERTIDO = {"codigo": "PATRON_TRAZO_INVERTIDO", "tipo": "error", "frecuencia": 3, "caracteres": ["水", "大", "人"]}
NO_SABE = {"codigo": "PATRON_NO_SABE", "tipo": "error", "frecuencia": 4, "caracteres": ["一", "七"]}
RECURRENTE = {"codigo": "PATRON_CARACTER_RECURRENTE", "tipo": "caracter", "frecuencia": 3, "caracteres": ["一"]}


# ---------- dominio: generar_ejercicio_adaptado ----------


@pytest.mark.parametrize("codigo, tipo", [
    ("PATRON_TRAZO_INVERTIDO", "trazo"),
    ("PATRON_TRAZO_LONGITUD", "trazo"),
    ("PATRON_TRAZO_POSICION", "trazo"),
    ("PATRON_TRAZO_FORMA", "trazo"),
    ("PATRON_PINYIN_INICIAL", "pinyin"),
    ("PATRON_PINYIN_FINAL", "pinyin"),
    ("PATRON_PINYIN_LECTURA", "pinyin"),
    ("PATRON_NO_SABE", "pinyin"),
    ("PATRON_SIGNIFICADO", "significado"),
    ("PATRON_CARACTER_RECURRENTE", "trazo"),
    ("PATRON_RETROCESO", "pinyin"),
])
def test_cada_patron_se_trabaja_con_su_tipo_de_ejercicio(codigo, tipo):
    (ejercicio,) = generar_ejercicio_adaptado({"codigo": codigo, "caracteres": ["人"]}, 3, 5)

    assert ejercicio == EjercicioAdaptado("人", tipo, 2, codigo)


def test_cubre_los_once_patrones_de_progreso():
    import ast
    from pathlib import Path

    patrones = Path(__file__).resolve().parents[2] / "progreso-flask" / "dominio" / "patrones.py"
    if not patrones.exists():
        pytest.skip("services/progreso-flask no está disponible")
    codigos = {
        n.value for n in ast.walk(ast.parse(patrones.read_text(encoding="utf-8")))
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith("PATRON_")
    }

    assert codigos == set(TIPO_POR_PATRON)


def test_respeta_el_orden_la_cantidad_y_lo_excluido():
    ejercicios = generar_ejercicio_adaptado(INVERTIDO, 3, 2, excluir={"水"})

    assert [e.caracter for e in ejercicios] == ["大", "人"]
    assert {e.patron for e in ejercicios} == {"PATRON_TRAZO_INVERTIDO"}


@pytest.mark.parametrize("patron", [
    {"codigo": "PATRON_DESCONOCIDO", "caracteres": ["人"]},
    {"codigo": "PATRON_NO_SABE", "caracteres": "人"},
    {"codigo": "PATRON_NO_SABE"},
    "PATRON_NO_SABE",
    None,
])
def test_un_patron_desconocido_o_mal_formado_no_genera_nada(patron):
    assert generar_ejercicio_adaptado(patron, 3, 3) == []


def test_ignora_caracteres_repetidos_o_vacios():
    patron = {"codigo": "PATRON_NO_SABE", "caracteres": ["一", "", None, "一", "七"]}

    assert [e.caracter for e in generar_ejercicio_adaptado(patron, 3, 5)] == ["一", "七"]


@pytest.mark.parametrize("dificultad, esperada", [(5, 4), (3, 2), (2, 1), (1, 1), (None, 1)])
def test_la_dificultad_baja_un_punto_sin_bajar_de_1(dificultad, esperada):
    assert dificultad_adaptada(dificultad) == esperada


def test_toma_del_patron_mas_relevante_y_completa_con_los_siguientes():
    ejercicios = adaptar_a_patrones([NO_SABE, INVERTIDO], 3, 3)

    assert [(e.caracter, e.tipo, e.patron) for e in ejercicios] == [
        ("一", "pinyin", "PATRON_NO_SABE"),
        ("七", "pinyin", "PATRON_NO_SABE"),
        ("水", "trazo", "PATRON_TRAZO_INVERTIDO"),
    ]


def test_un_caracter_queda_con_el_patron_mas_relevante():
    ejercicios = adaptar_a_patrones([NO_SABE, RECURRENTE], 3, 3)

    assert [(e.caracter, e.patron) for e in ejercicios] == [("一", "PATRON_NO_SABE"), ("七", "PATRON_NO_SABE")]


def test_sin_patrones_no_hay_adaptados():
    assert adaptar_a_patrones([], 3, 3) == []
    assert adaptar_a_patrones(None, 3, 3) == []


# ---------- el motor del tutor ----------


def test_el_motor_ejecuta_generar_ejercicio_adaptado():
    motor = MotorTutorMock(catalogo=None)

    ejercicios = motor.generar_ejercicio_adaptado(INVERTIDO, dificultad=4, cantidad=2)

    assert ejercicios == [
        EjercicioAdaptado("水", "trazo", 3, "PATRON_TRAZO_INVERTIDO"),
        EjercicioAdaptado("大", "trazo", 3, "PATRON_TRAZO_INVERTIDO"),
    ]


def test_el_servicio_usa_el_metodo_del_motor():
    """Un motor que redefine generar_ejercicio_adaptado cambia lo que se arma."""

    class MotorPropio(MotorFalso):
        def generar_ejercicio_adaptado(self, patron, dificultad, cantidad, excluir=()):
            return [EjercicioAdaptado("龙", "trazo", 1, patron["codigo"])][:cantidad]

    servicio = SesionEstudioService(MotorPropio(), None, ProgresoFalso(patrones=[INVERTIDO]))

    _, adaptados, _, _ = servicio._elegir_caracteres(USUARIO, {}, 3)

    assert [(e.caracter, e.patron) for e in adaptados] == [("龙", "PATRON_TRAZO_INVERTIDO")]


# ---------- cliente de progreso ----------


def test_pide_los_patrones_a_progreso():
    transporte = TransporteFalso((200, {"usuario_id": str(USUARIO), "ventana_dias": 14, "patrones": [INVERTIDO]}))

    patrones = ProgresoRemoto(cliente(transporte)[0]).patrones_de_error(USUARIO)

    assert patrones == [INVERTIDO]
    assert transporte.llamadas[0][1] == f"http://servicio:5000/api/v2/progreso/{USUARIO}/patrones/"


@pytest.mark.parametrize("respuestas", [
    [TimeoutError()] * 3,
    [(500, "{}")] * 3,
    [(200, {"patrones": "no es lista"})],
    [(200, ["no", "es", "objeto"])],
])
def test_si_progreso_falla_no_hay_patrones(respuestas):
    progreso = ProgresoRemoto(cliente(TransporteFalso(*respuestas))[0])

    assert progreso.patrones_de_error(USUARIO) == []


# ---------- la sesión armada ----------


def crear(client, progreso, nivel_hsk=2):
    resp = client.post("/api/v2/sesiones/", json={"usuario_id": str(USUARIO), "nivel_hsk": nivel_hsk})
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()["ejercicios"]


def test_la_sesion_incluye_ejercicios_adaptados_despues_de_los_vencidos(client, progreso):
    progreso.vencidos = ["人"]
    progreso.patrones = [INVERTIDO]
    progreso.refuerzos = ["目"]

    ejercicios = crear(client, progreso)

    resumen = [(e["caracter"], e["tipo"], e["es_refuerzo"], e["patron"]) for e in ejercicios]
    assert resumen[0] == ("人", "significado", True, None)
    # 人 ya está como vencido: el patrón aporta 水 y 大, con dificultad 3 - 1.
    assert resumen[1:3] == [
        ("水", "trazo", True, "PATRON_TRAZO_INVERTIDO"),
        ("大", "trazo", True, "PATRON_TRAZO_INVERTIDO"),
    ]
    assert [e["dificultad"] for e in ejercicios[1:3]] == [2, 2]
    assert resumen[3] == ("目", "trazo", True, None)
    assert all(e["patron"] is None for e in ejercicios[4:])
    assert len({e["caracter"] for e in ejercicios}) == len(ejercicios) == 7


def test_como_mucho_tres_adaptados(client, progreso):
    progreso.patrones = [INVERTIDO, NO_SABE]

    ejercicios = crear(client, progreso)

    assert [e["caracter"] for e in ejercicios if e["patron"]] == ["水", "大", "人"]


def test_un_refuerzo_que_ya_es_adaptado_no_se_repite(client, progreso):
    progreso.patrones = [NO_SABE]
    progreso.refuerzos = ["一", "目"]

    ejercicios = crear(client, progreso)

    caracteres = [e["caracter"] for e in ejercicios]
    assert caracteres.count("一") == 1
    assert ejercicios[0]["patron"] == "PATRON_NO_SABE"
    assert "目" in caracteres


def test_sin_patrones_la_sesion_es_la_de_siempre(client, progreso):
    ejercicios = crear(client, progreso)

    assert all(e["patron"] is None for e in ejercicios)
    assert ejercicios[0]["caracter"] == "目"


def test_con_progreso_caido_la_sesion_se_arma_sin_adaptados(client, progreso):
    progreso.patrones = [INVERTIDO]
    progreso.caido = True

    ejercicios = crear(client, progreso)

    assert all(e["patron"] is None for e in ejercicios)


def test_el_detalle_y_responder_devuelven_el_patron(client, progreso):
    progreso.patrones = [NO_SABE]
    creada = client.post("/api/v2/sesiones/", json={"usuario_id": str(USUARIO), "nivel_hsk": 2}).get_json()
    ejercicio = creada["ejercicios"][0]

    sesion = client.get(f"/api/v2/sesiones/{creada['id']}/").get_json()
    respuesta = client.post(
        f"/api/v2/ejercicios/{ejercicio['id']}/responder/", json={"acerto": False, "codigo_error": "NO_SABE"}
    ).get_json()

    assert sesion["ejercicios"][0]["patron"] == "PATRON_NO_SABE"
    assert respuesta["ejercicio"]["patron"] == "PATRON_NO_SABE"



# ---------- cupo compartido de adaptados y refuerzos (revisión de #53) ----------


def grupos(ejercicios):
    """(vencidos, adaptados, refuerzos, nuevos) por carácter, según los campos del JSON."""
    vencidos = [e["caracter"] for e in ejercicios if e["tipo"] == "significado" and e["es_refuerzo"]]
    adaptados = [e["caracter"] for e in ejercicios if e["patron"]]
    refuerzos = [e["caracter"] for e in ejercicios if e["tipo"] == "trazo" and e["es_refuerzo"] and not e["patron"]]
    nuevos = [e["caracter"] for e in ejercicios if not e["es_refuerzo"]]
    return vencidos, adaptados, refuerzos, nuevos


def test_tres_adaptados_dejan_cero_refuerzos(client, progreso):
    progreso.patrones = [INVERTIDO]
    progreso.refuerzos = ["目", "且", "月"]
    pedidos = []
    original = progreso.caracteres_a_reforzar
    progreso.caracteres_a_reforzar = lambda u, limite=3: (pedidos.append(limite), original(u, limite))[1]

    _, adaptados, refuerzos, nuevos = grupos(crear(client, progreso))

    assert adaptados == ["水", "大", "人"]
    assert refuerzos == []
    # Con el cupo lleno ni se piden refuerzos.
    assert pedidos == []
    assert len(nuevos) == 4


def test_un_adaptado_deja_hasta_dos_refuerzos(client, progreso):
    progreso.patrones = [RECURRENTE]
    progreso.refuerzos = ["目", "且", "月"]

    _, adaptados, refuerzos, nuevos = grupos(crear(client, progreso))

    assert adaptados == ["一"]
    assert refuerzos == ["目", "且"]
    assert len(nuevos) == 4


def test_un_refuerzo_repetido_no_ocupa_lugar_del_cupo(client, progreso):
    # 一 es adaptado y también el primer refuerzo: se pide con margen y los
    # 2 lugares libres quedan para 目 y 且.
    progreso.patrones = [RECURRENTE]
    progreso.refuerzos = ["一", "目", "且", "月"]

    _, adaptados, refuerzos, _ = grupos(crear(client, progreso))

    assert (adaptados, refuerzos) == (["一"], ["目", "且"])


def test_cuatro_vencidos_y_tres_adaptados_dan_ocho_con_un_nuevo(client, progreso):
    progreso.vencidos = ["一", "二", "三", "四"]
    progreso.patrones = [INVERTIDO]
    progreso.refuerzos = ["目", "且"]

    ejercicios = crear(client, progreso)

    vencidos, adaptados, refuerzos, nuevos = grupos(ejercicios)
    assert len(ejercicios) == 8
    assert (len(vencidos), len(adaptados), len(refuerzos), len(nuevos)) == (4, 3, 0, 1)
    assert [e["caracter"] for e in ejercicios[:4]] == ["一", "二", "三", "四"]


def test_nunca_pasa_de_ocho_ejercicios(client, progreso):
    progreso.vencidos = ["一", "二", "三", "四", "五"]
    progreso.patrones = [INVERTIDO, NO_SABE]
    progreso.refuerzos = ["目", "且", "月"]

    assert len(crear(client, progreso)) == 8


def test_sin_patrones_por_progreso_caido_la_sesion_es_la_de_rf_ia_02(client, progreso):
    # Solo falla patrones/ (ProgresoRemoto devuelve [] si no responde): vencidos
    # primero, hasta 3 refuerzos y los nuevos completan 7.
    progreso.vencidos = ["人"]
    progreso.patrones = [INVERTIDO]
    progreso.refuerzos = ["目", "且", "月"]
    progreso.patrones_de_error = lambda usuario_id: []

    ejercicios = crear(client, progreso)

    vencidos, adaptados, refuerzos, nuevos = grupos(ejercicios)
    assert (vencidos, adaptados, refuerzos) == (["人"], [], ["目", "且", "月"])
    assert len(nuevos) == 3
    assert len(ejercicios) == 7
