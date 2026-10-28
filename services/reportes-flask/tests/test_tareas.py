"""Configuración de Celery y tareas llamadas directamente, sin Redis ni worker."""

import config
import tareas
from clientes import ServicioNoDisponible
from dominio.excepciones import DependenciaNoDisponible, ErrorReporte
from fabricas import crear_dependencias
from tareas import celery_app, generar_reporte_progreso, notificar_sesion_lista, ping
from tests.conftest import PROGRESO, USUARIO, ProgresoFalso

# ---------------------------------------------------------------- configuración


def test_ajustes_de_celery():
    conf = celery_app.conf

    assert conf.result_expires == 86400
    assert conf.task_track_started is True
    assert conf.task_soft_time_limit == 30
    assert conf.worker_prefetch_multiplier == 1


def test_solo_json_en_la_cola_y_en_los_resultados():
    conf = celery_app.conf

    assert conf.task_serializer == "json"
    assert conf.result_serializer == "json"
    assert list(conf.accept_content) == ["json"]


def test_broker_desde_redis_url():
    assert celery_app.conf.broker_url == config.desde_entorno()["REDIS_URL"]


def test_tareas_registradas_por_nombre():
    for nombre in ("ping", "generar_reporte_progreso", "notificar_sesion_lista"):
        assert nombre in celery_app.tasks


def test_ping_responde_pong():
    assert ping() == "pong"
    assert ping.apply().get() == "pong"


# ---------------------------------------------------------------- reporte


def test_reporte_con_los_campos_acordados(progreso):
    reporte = generar_reporte_progreso.apply(args=[USUARIO]).get()

    assert list(reporte) == [
        "usuario_id", "nivel_hsk", "nivel_max_desbloqueado", "tasa_acierto",
        "total_dominados", "total_por_reforzar", "caracteres_dominados",
        "caracteres_debiles", "proximo_repaso", "actualizado_en", "generado_en",
    ]
    assert reporte["caracteres_debiles"] == PROGRESO["caracteres_debiles"]
    assert reporte["generado_en"].endswith("Z")
    assert progreso.consultas == [USUARIO]


def test_progreso_caido_reintenta_3_veces_y_termina_en_error(dependencias):
    dependencias.progreso = ProgresoFalso(caido=True)

    resultado = generar_reporte_progreso.apply(args=[USUARIO])

    assert resultado.state == "FAILURE"
    assert isinstance(resultado.result, DependenciaNoDisponible)
    assert resultado.result.codigo == "DEPENDENCIA_NO_DISPONIBLE"
    # 1 intento + 3 reintentos.
    assert len(dependencias.progreso.consultas) == 4


def test_backoff_1_2_4_sin_azar(dependencias, monkeypatch):
    dependencias.progreso = ProgresoFalso(caido=True)
    esperas = []
    original = generar_reporte_progreso.retry

    def retry(*args, **kwargs):
        esperas.append(kwargs.get("countdown"))
        return original(*args, **kwargs)

    monkeypatch.setattr(generar_reporte_progreso, "retry", retry)

    generar_reporte_progreso.apply(args=[USUARIO])

    # El cuarto llamado a retry ya supera max_retries y no espera: falla.
    assert esperas[:3] == [1, 2, 4]
    assert generar_reporte_progreso.retry_jitter is False


def test_peor_caso_hasta_error_menos_de_30_s():
    timeout = config.desde_entorno()["HTTP_TIMEOUT"]
    intentos = tareas.MAX_REINTENTOS + 1
    esperas = sum(tareas.BACKOFF_SEGUNDOS * 2 ** n for n in range(tareas.MAX_REINTENTOS))

    assert intentos * timeout + esperas < 30
    # Medido en Docker con progreso detenido: la resolución DNS suma ~1 s por
    # intento por encima del timeout.
    assert intentos * (timeout + 1) + esperas < 30


def test_cliente_de_la_tarea_sin_reintentos_http():
    deps = crear_dependencias(config.desde_entorno(), redis_cliente=None)

    assert deps.progreso._cliente.reintentos == 0


def test_progreso_4xx_no_se_reintenta(dependencias):
    dependencias.progreso = ProgresoFalso(caido=True, estado=400)

    resultado = generar_reporte_progreso.apply(args=[USUARIO])

    assert resultado.state == "FAILURE"
    assert isinstance(resultado.result, ErrorReporte)
    assert resultado.result.codigo == "ERROR_INTERNO"
    assert len(dependencias.progreso.consultas) == 1


def test_error_reporte_se_reconstruye_con_cls_args():
    # Así lo recrea Celery desde el JSON guardado en Redis.
    error = DependenciaNoDisponible()
    copia = DependenciaNoDisponible(*error.args)

    assert (copia.codigo, copia.mensaje) == (error.codigo, error.mensaje)


def test_servicio_no_disponible_no_sale_de_la_tarea(dependencias):
    # Nunca llega al backend un error de clientes.py con la URL interna.
    dependencias.progreso = ProgresoFalso(caido=True)

    resultado = generar_reporte_progreso.apply(args=[USUARIO])

    assert not isinstance(resultado.result, ServicioNoDisponible)
    assert "http" not in str(resultado.result)


# ---------------------------------------------------------------- notificaciones


def test_notificar_guarda_la_notificacion(notificaciones, caplog):
    with caplog.at_level("INFO"):
        notificar_sesion_lista.apply(args=[USUARIO, 7])

    [notificacion] = notificaciones.listar(USUARIO)
    assert notificacion["tipo"] == "sesion_lista"
    assert notificacion["sesion_id"] == 7
    assert notificacion["creada_en"].endswith("Z")
    assert notificaciones.caducidad[f"notificaciones:{USUARIO}"] == 7 * 24 * 3600
    assert f"Sesión 7 lista para {USUARIO}" in caplog.text


def test_notificar_guarda_solo_las_ultimas_20(notificaciones):
    for sesion_id in range(1, 26):
        notificar_sesion_lista.apply(args=[USUARIO, sesion_id])

    ids = [n["sesion_id"] for n in notificaciones.listar(USUARIO)]
    assert ids == list(range(25, 5, -1))


def test_notificar_descarta_usuario_invalido(notificaciones):
    notificar_sesion_lista.apply(args=["no-es-uuid", 1])

    assert notificaciones.listas == {}


def test_notificar_no_guarda_resultado():
    assert notificar_sesion_lista.ignore_result is True
