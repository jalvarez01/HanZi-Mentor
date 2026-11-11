"""Dominio sin base de datos: repaso espaciado (port de RepasoEspaciadoTest de
agente-tutor/tutor/tests.py) y reglas de acierto y error."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from dominio import progreso as reglas
from dominio.repaso import (
    actualizar_tasa_acierto,
    calcular_proximo_repaso,
    esta_pendiente,
)

AHORA = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


@dataclass
class Progreso:
    """Doble de la entidad con los mismos defaults que el modelo."""

    nivel_max_desbloqueado: int = 1
    caracteres_dominados: list = field(default_factory=list)
    errores_frecuentes: dict = field(default_factory=dict)
    aciertos_consecutivos: dict = field(default_factory=dict)
    agenda_repaso: dict = field(default_factory=dict)
    errores_por_codigo: dict = field(default_factory=dict)
    historial_errores: list = field(default_factory=list)
    proximo_repaso: datetime | None = None


# ---------- repaso espaciado ----------


def test_el_intervalo_crece_con_la_racha():
    assert calcular_proximo_repaso(0, acerto=True, desde=AHORA) == AHORA + timedelta(days=1)
    assert calcular_proximo_repaso(2, acerto=True, desde=AHORA) == AHORA + timedelta(days=7)


def test_fallar_acerca_el_repaso():
    assert calcular_proximo_repaso(5, acerto=False, desde=AHORA) == AHORA + timedelta(hours=12)


def test_el_intervalo_tiene_techo():
    assert calcular_proximo_repaso(99, acerto=True, desde=AHORA) == AHORA + timedelta(days=90)


def test_sin_desde_usa_ahora_en_utc():
    cuando = calcular_proximo_repaso(0, acerto=True)

    assert cuando.tzinfo == timezone.utc


def test_pendiente_si_nunca_se_agendo():
    assert esta_pendiente(None)
    assert not esta_pendiente(AHORA + timedelta(days=1), momento=AHORA)
    assert esta_pendiente(AHORA - timedelta(seconds=1), momento=AHORA)


def test_la_tasa_sube_al_acertar_y_baja_al_fallar():
    assert actualizar_tasa_acierto(0.5, acerto=True) > 0.5
    assert actualizar_tasa_acierto(0.5, acerto=False) < 0.5


def test_la_tasa_nunca_sale_del_rango():
    assert actualizar_tasa_acierto(1.0, acerto=True) <= 1.0
    assert actualizar_tasa_acierto(0.0, acerto=False) >= 0.0


# ---------- reglas de progreso ----------


def test_fallar_suma_error_y_corta_racha():
    progreso = Progreso(aciertos_consecutivos={"学": 3})

    reglas.registrar_error(progreso, "学")

    assert progreso.errores_frecuentes == {"学": 1}
    assert reglas.racha_de(progreso, "学") == 0


def test_fallar_quita_de_dominados():
    progreso = Progreso(caracteres_dominados=["学", "校"])

    reglas.registrar_error(progreso, "学")

    assert progreso.caracteres_dominados == ["校"]


def test_acertar_sin_errores_suma_racha_y_domina():
    progreso = Progreso()

    reglas.registrar_acierto(progreso, "学")

    assert reglas.racha_de(progreso, "学") == 1
    assert progreso.caracteres_dominados == ["学"]


def test_acertar_descuenta_un_error_y_no_domina_si_quedan():
    progreso = Progreso(errores_frecuentes={"学": 2})

    reglas.registrar_acierto(progreso, "学")

    assert progreso.errores_frecuentes == {"学": 1}
    assert progreso.caracteres_dominados == []


def test_acertar_el_ultimo_error_lo_borra_y_domina():
    progreso = Progreso(errores_frecuentes={"学": 1})

    reglas.registrar_acierto(progreso, "学")

    assert progreso.errores_frecuentes == {}
    assert progreso.caracteres_dominados == ["学"]


def test_acertar_dos_veces_no_duplica_dominados():
    progreso = Progreso()

    reglas.registrar_respuesta(progreso, "学", acerto=True)
    reglas.registrar_respuesta(progreso, "学", acerto=True)

    assert progreso.caracteres_dominados == ["学"]
    assert reglas.racha_de(progreso, "学") == 2


def test_agendar_repaso_guarda_iso_y_el_mas_cercano():
    progreso = Progreso()
    lejos, cerca = AHORA + timedelta(days=7), AHORA + timedelta(days=1)

    reglas.agendar_repaso(progreso, "学", lejos)
    reglas.agendar_repaso(progreso, "校", cerca)
    reglas.agendar_repaso(progreso, "人", lejos)

    assert progreso.agenda_repaso["学"] == lejos.isoformat()
    assert progreso.proximo_repaso == cerca


def test_desbloquear_tiene_tope():
    progreso = Progreso(nivel_max_desbloqueado=5)

    reglas.desbloquear_siguiente_nivel(progreso)
    reglas.desbloquear_siguiente_nivel(progreso)

    assert progreso.nivel_max_desbloqueado == 6


def test_peores_caracteres_ordena_de_peor_a_mejor():
    errores = {"目": 2, "人": 5, "且": 3}

    assert reglas.peores_caracteres(errores, 2) == [("人", 5), ("且", 3)]
    assert reglas.peores_caracteres(None, 3) == []


# ---------- historial de errores (RF-IA-01) ----------


def test_anotar_error_guarda_la_entrada_y_suma_al_codigo():
    progreso = Progreso()

    assert reglas.anotar_error(progreso, "学", "PINYIN_INICIAL", AHORA, dominado=True)
    reglas.anotar_error(progreso, "校", "PINYIN_INICIAL", AHORA)

    assert progreso.historial_errores[0] == {
        "codigo": "PINYIN_INICIAL",
        "caracter": "学",
        "fecha": "2026-10-23T12:00:00+00:00",
        "origen": "sesion",
        "dominado": True,
    }
    assert progreso.historial_errores[1]["dominado"] is False
    assert progreso.errores_por_codigo == {"PINYIN_INICIAL": 2}


def test_un_fallo_sin_codigo_va_al_historial_pero_no_al_conteo():
    progreso = Progreso()

    reglas.anotar_error(progreso, "学", None, AHORA)

    assert progreso.historial_errores[0]["codigo"] is None
    assert progreso.errores_por_codigo == {}


def test_el_historial_guarda_los_ultimos_50_de_cada_origen():
    progreso = Progreso()
    for i in range(55):
        reglas.anotar_error(progreso, "学", "NO_SABE", AHORA + timedelta(minutes=i))
    for i in range(52):
        # Cada 3 minutos: no son reintentos.
        reglas.anotar_error(
            progreso, "人", "TRAZO_INVERTIDO", AHORA + timedelta(minutes=3 * i), origen="trazos"
        )

    de_sesion = [e for e in progreso.historial_errores if e["origen"] == "sesion"]
    de_trazos = [e for e in progreso.historial_errores if e["origen"] == "trazos"]
    assert (len(de_sesion), len(de_trazos)) == (50, 50)
    # Se van los más viejos y el total acumulado no se recorta.
    assert de_sesion[0]["fecha"] == (AHORA + timedelta(minutes=5)).isoformat()
    assert de_trazos[0]["fecha"] == (AHORA + timedelta(minutes=6)).isoformat()
    assert progreso.errores_por_codigo == {"NO_SABE": 55, "TRAZO_INVERTIDO": 52}


def test_reintento_del_mismo_trazo_en_menos_de_dos_minutos_cuenta_una_vez():
    progreso = Progreso()

    assert reglas.anotar_error(progreso, "人", "TRAZO_INVERTIDO", AHORA, origen="trazos")
    assert not reglas.anotar_error(
        progreso, "人", "TRAZO_INVERTIDO", AHORA + timedelta(seconds=119), origen="trazos"
    )
    # Otro código, otro carácter o pasados los dos minutos: sí se anota.
    assert reglas.anotar_error(progreso, "人", "TRAZO_CORTO", AHORA + timedelta(seconds=30), origen="trazos")
    assert reglas.anotar_error(progreso, "大", "TRAZO_INVERTIDO", AHORA + timedelta(seconds=40), origen="trazos")
    assert reglas.anotar_error(
        progreso, "人", "TRAZO_INVERTIDO", AHORA + timedelta(seconds=120), origen="trazos"
    )

    assert len(progreso.historial_errores) == 4
    assert progreso.errores_por_codigo == {"TRAZO_INVERTIDO": 3, "TRAZO_CORTO": 1}


def test_en_sesion_dos_fallos_seguidos_se_anotan_los_dos():
    progreso = Progreso()

    assert reglas.anotar_error(progreso, "人", "NO_SABE", AHORA)
    assert reglas.anotar_error(progreso, "人", "NO_SABE", AHORA + timedelta(seconds=5))

    assert len(progreso.historial_errores) == 2
