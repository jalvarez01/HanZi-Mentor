"""Cálculo de desempeño (RF-IA-05): en cuanto termina la sesión,
SesionEstudio.calcular_desempeno() procesa la duración y la fecha y los
resultados quedan registrados."""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from dominio.desempeno import (
    calcular_desempeno,
    duracion_en_segundos,
    fecha_de_cierre,
    registrar_desempeno,
    resumen,
)
from modelos import Ejercicio, SesionEstudio
from servicio import ResponderEjercicioService
from tests.conftest import USUARIO, ProgresoFalso
from tests.test_sesiones import responder_todo

INICIO = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)


def ejercicio(tipo="trazo", acerto=True, minuto=1, respondido=True):
    return SimpleNamespace(
        tipo=tipo,
        respondido=respondido,
        fue_correcto=acerto if respondido else None,
        respondido_en=INICIO + timedelta(minutes=minuto) if respondido else None,
    )


def sesion(ejercicios, estado="completada", completada_en=None, duracion_min=10):
    return SimpleNamespace(
        id=7, estado=estado, creada_en=INICIO, completada_en=completada_en,
        duracion_estimada_min=duracion_min, ejercicios=ejercicios,
    )


# ---------- dominio ----------


def test_calcula_duracion_fecha_y_resultados():
    s = sesion(
        [ejercicio("trazo", True, 2), ejercicio("trazo", False, 4), ejercicio("pinyin", True, 6), ejercicio("significado", True, 8)],
        completada_en=INICIO + timedelta(minutes=8, seconds=30),
    )

    d = calcular_desempeno(s)

    assert (d.sesion_id, d.creada_en, d.completada_en) == (7, INICIO, INICIO + timedelta(minutes=8, seconds=30))
    assert (d.duracion_seg, d.duracion_estimada_min, d.dentro_del_tiempo) == (510, 10, True)
    assert (d.total, d.aciertos, d.fallos, d.tasa_acierto, d.segundos_por_ejercicio) == (4, 3, 1, 0.75, 128)
    assert d.por_tipo == {
        "trazo": {"total": 2, "aciertos": 1},
        "pinyin": {"total": 1, "aciertos": 1},
        "significado": {"total": 1, "aciertos": 1},
    }


def test_una_sesion_en_curso_no_tiene_desempeno():
    assert calcular_desempeno(sesion([ejercicio(), ejercicio(respondido=False)], estado="activa")) is None


def test_sin_fecha_guardada_usa_la_ultima_respuesta():
    """Las sesiones cerradas antes de RF-IA-05 no tienen completada_en."""
    s = sesion([ejercicio(minuto=3), ejercicio(minuto=12), ejercicio(minuto=5)])

    assert fecha_de_cierre(s) == INICIO + timedelta(minutes=12)
    assert calcular_desempeno(s).duracion_seg == 720


def test_completada_sin_respuestas_ni_fecha_no_tiene_desempeno():
    assert calcular_desempeno(sesion([])) is None


@pytest.mark.parametrize("minutos, estimada, dentro", [(10, 10, True), (10.02, 10, False), (3, 5, True), (61, 60, False)])
def test_dentro_del_tiempo_compara_con_la_duracion_estimada(minutos, estimada, dentro):
    s = sesion([ejercicio()], completada_en=INICIO + timedelta(minutes=minutos), duracion_min=estimada)

    assert calcular_desempeno(s).dentro_del_tiempo is dentro


def test_la_duracion_nunca_es_negativa():
    assert duracion_en_segundos(INICIO, INICIO - timedelta(seconds=5)) == 0
    assert duracion_en_segundos(INICIO, INICIO + timedelta(seconds=59.9)) == 59


@pytest.mark.parametrize("resultados, tasa", [([True, True, False], 0.67), ([False], 0.0), ([True], 1.0)])
def test_la_tasa_es_de_la_sesion_con_dos_decimales(resultados, tasa):
    s = sesion([ejercicio(acerto=a, minuto=i + 1) for i, a in enumerate(resultados)])

    assert calcular_desempeno(s).tasa_acierto == tasa


def test_registrar_copia_fecha_duracion_y_aciertos_en_la_sesion():
    s = sesion([ejercicio(acerto=True), ejercicio(acerto=False, minuto=2)], completada_en=INICIO + timedelta(minutes=2))

    registrar_desempeno(s, calcular_desempeno(s))

    assert (s.completada_en, s.duracion_seg, s.aciertos) == (INICIO + timedelta(minutes=2), 120, 1)


def test_resumen_de_varias_sesiones():
    a = calcular_desempeno(sesion([ejercicio(acerto=True), ejercicio(acerto=False, minuto=2)]))
    b = calcular_desempeno(sesion([ejercicio(acerto=True, minuto=4)]))

    assert resumen([a, b]) == {"sesiones": 2, "ejercicios": 3, "aciertos": 2, "tasa_acierto": 0.67, "duracion_seg": 360}
    assert resumen([]) == {"sesiones": 0, "ejercicios": 0, "aciertos": 0, "tasa_acierto": 0.0, "duracion_seg": 0}


# ---------- la entidad SesionEstudio ----------


def test_la_entidad_ejecuta_calcular_desempeno():
    s = SesionEstudio(
        id=1, usuario_id=USUARIO, nivel_hsk=1, dificultad=2, estado="completada",
        creada_en=INICIO, duracion_estimada_min=5, completada_en=INICIO + timedelta(minutes=6),
    )
    s.ejercicios = [
        Ejercicio(caracter="人", tipo="trazo", dificultad=2, respondido=True, fue_correcto=True,
                  respondido_en=INICIO + timedelta(minutes=6)),
    ]

    d = s.calcular_desempeno()

    assert (d.duracion_seg, d.dentro_del_tiempo, d.aciertos, d.tasa_acierto) == (360, False, 1, 1.0)


# ---------- al cerrar la sesión ----------


def correr_reloj(sesion_db, sesion_id, minutos):
    """La sesión empezó hace `minutos` (las respuestas usan el reloj real)."""
    s = sesion_db.get(SesionEstudio, sesion_id)
    s.creada_en = s.creada_en - timedelta(minutes=minutos)
    sesion_db.commit()


def test_la_respuesta_que_cierra_trae_el_desempeno(client, crear_sesion, sesion_db):
    creada = crear_sesion()
    correr_reloj(sesion_db, creada["id"], 4)
    cuerpos = {0: {"acerto": False, "codigo_error": "NO_SABE"}}

    ultima = responder_todo(client, creada["ejercicios"], cuerpos).get_json()

    d = ultima["desempeno"]
    total = len(creada["ejercicios"])
    assert list(d) == [
        "sesion_id", "creada_en", "completada_en", "duracion_seg", "duracion_estimada_min",
        "dentro_del_tiempo", "segundos_por_ejercicio", "total", "aciertos", "fallos", "tasa_acierto", "por_tipo",
    ]
    assert (d["sesion_id"], d["total"], d["aciertos"], d["fallos"]) == (creada["id"], total, total - 1, 1)
    assert d["tasa_acierto"] == round((total - 1) / total, 2)
    assert 240 <= d["duracion_seg"] < 250 and d["dentro_del_tiempo"] is True
    assert d["completada_en"].endswith("Z") and d["creada_en"].endswith("Z")
    assert sum(t["total"] for t in d["por_tipo"].values()) == total


def test_las_respuestas_anteriores_no_traen_desempeno(client, crear_sesion):
    ejercicios = crear_sesion()["ejercicios"]

    datos = client.post(f"/api/v2/ejercicios/{ejercicios[0]['id']}/responder/", json={"acerto": True}).get_json()

    assert "desempeno" not in datos


def test_el_desempeno_queda_registrado_en_la_sesion(client, crear_sesion, sesion_db):
    creada = crear_sesion()
    ultima = responder_todo(client, creada["ejercicios"], {}).get_json()

    s = sesion_db.get(SesionEstudio, creada["id"])
    assert s.completada_en is not None
    assert (s.duracion_seg, s.aciertos) == (ultima["desempeno"]["duracion_seg"], len(creada["ejercicios"]))
    assert s.completada_en == max(e.respondido_en for e in s.ejercicios)


def test_con_progreso_caido_el_desempeno_se_registra_igual(client, crear_sesion, progreso):
    creada = crear_sesion()
    progreso.caido = True

    ultima = responder_todo(client, creada["ejercicios"], {}).get_json()

    assert list(ultima)[-2:] == ["desempeno", "aviso"]
    assert ultima["desempeno"]["aciertos"] == len(creada["ejercicios"])


def test_el_servicio_usa_el_momento_de_la_ultima_respuesta(app, crear_sesion, sesion_db):
    creada = crear_sesion()
    momento = datetime.now(timezone.utc) + timedelta(minutes=30)
    servicio = ResponderEjercicioService(ProgresoFalso(), reloj=lambda: momento)

    for e in creada["ejercicios"]:
        resultado = servicio.responder(sesion_db, e["id"], True)

    assert resultado["desempeno"].completada_en == momento
    assert resultado["desempeno"].dentro_del_tiempo is False


# ---------- GET /api/v2/sesiones/<id>/desempeno/ ----------


def test_detalle_del_desempeno_de_una_sesion_terminada(client, crear_sesion):
    creada = crear_sesion()
    ultima = responder_todo(client, creada["ejercicios"], {}).get_json()

    resp = client.get(f"/api/v2/sesiones/{creada['id']}/desempeno/")

    assert resp.status_code == 200
    assert resp.get_json() == ultima["desempeno"]


@pytest.mark.parametrize("idioma, mensaje", [
    ("es", "La sesión {} todavía no terminó: no tiene desempeño."),
    ("en", "Session {} has not finished yet: it has no performance."),
])
def test_una_sesion_en_curso_da_409(client, crear_sesion, idioma, mensaje):
    creada = crear_sesion()

    resp = client.get(f"/api/v2/sesiones/{creada['id']}/desempeno/", headers={"Accept-Language": idioma})

    assert resp.status_code == 409
    assert resp.get_json() == {"error": mensaje.format(creada["id"]), "codigo": "SESION_NO_COMPLETADA"}


def test_desempeno_de_una_sesion_que_no_existe_da_404(client):
    resp = client.get("/api/v2/sesiones/999/desempeno/")

    assert resp.status_code == 404
    assert resp.get_json()["codigo"] == "NO_ENCONTRADO"


# ---------- GET /api/v2/sesiones/desempeno/?usuario_id= ----------


def test_historial_de_las_sesiones_terminadas(client, crear_sesion):
    primera = crear_sesion()
    responder_todo(client, primera["ejercicios"], {0: {"acerto": False}})
    segunda = crear_sesion()
    responder_todo(client, segunda["ejercicios"], {})
    crear_sesion()                                   # en curso: no entra
    otro = crear_sesion(usuario=uuid.uuid4())        # de otro usuario: no entra
    responder_todo(client, otro["ejercicios"], {})

    datos = client.get(f"/api/v2/sesiones/desempeno/?usuario_id={USUARIO}").get_json()

    assert list(datos) == ["usuario_id", "resumen", "sesiones"]
    assert datos["usuario_id"] == str(USUARIO)
    assert [s["sesion_id"] for s in datos["sesiones"]] == [segunda["id"], primera["id"]]
    total = len(primera["ejercicios"]) + len(segunda["ejercicios"])
    assert datos["resumen"]["sesiones"] == 2
    assert (datos["resumen"]["ejercicios"], datos["resumen"]["aciertos"]) == (total, total - 1)


def test_historial_respeta_el_limite(client, crear_sesion):
    for _ in range(3):
        responder_todo(client, crear_sesion()["ejercicios"], {})

    datos = client.get(f"/api/v2/sesiones/desempeno/?usuario_id={USUARIO}&limite=2").get_json()

    assert len(datos["sesiones"]) == 2 and datos["resumen"]["sesiones"] == 2


def test_historial_vacio(client):
    datos = client.get(f"/api/v2/sesiones/desempeno/?usuario_id={uuid.uuid4()}").get_json()

    assert datos["sesiones"] == [] and datos["resumen"]["tasa_acierto"] == 0.0


@pytest.mark.parametrize("consulta", ["", "?usuario_id=no-es-uuid", f"?usuario_id={USUARIO}&limite=0", f"?usuario_id={USUARIO}&limite=51"])
def test_historial_valida_la_entrada(client, consulta):
    resp = client.get(f"/api/v2/sesiones/desempeno/{consulta}", headers={"Accept-Language": "en"})

    assert resp.status_code == 400
    assert resp.get_json()["codigo"] == "ENTRADA_INVALIDA"
