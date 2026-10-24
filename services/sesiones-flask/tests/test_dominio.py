"""Dominio sin base de datos ni HTTP: Builder, ciclo de vida de la sesión y repaso.

Incluye el port de SesionEstudioBuilderTest de agente-tutor/tutor/tests.py.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest

from dominio import sesion as reglas
from dominio.builder import MAX_EJERCICIOS, SesionEstudioBuilder
from dominio.excepciones import NivelNoPermitidoError, SesionInvalidaError
from dominio.repaso import calcular_proximo_repaso, racha_previa

AHORA = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


class RepositorioEspia:
    def __init__(self):
        self.guardados = []

    def guardar_sesion(self, datos, ejercicios):
        self.guardados.append((datos, ejercicios))
        return datos


@dataclass
class Ej:
    respondido: bool = False


@dataclass
class Sesion:
    estado: str = "activa"
    ejercicios: list = field(default_factory=list)


def builder_valido():
    return (
        SesionEstudioBuilder()
        .para_usuario(uuid.uuid4(), nivel_max_desbloqueado=3)
        .en_nivel(2)
        .con_dificultad(3)
    )


# ---------- Builder ----------


def test_no_persiste_si_faltan_ejercicios():
    repo = RepositorioEspia()
    builder = builder_valido().agregar_contenido_nuevo(["人"])

    with pytest.raises(SesionInvalidaError):
        builder.build(repo)
    assert repo.guardados == []


def test_refuerzos_primero_con_tipo_trazo():
    repo = RepositorioEspia()

    builder_valido().agregar_refuerzos(["目"]).agregar_contenido_nuevo(["学", "校"]).build(repo)

    datos, ejercicios = repo.guardados[0]
    assert datos["estado"] == "activa"
    assert ejercicios[0] == {"caracter": "目", "tipo": "trazo", "dificultad": 3, "es_refuerzo": True}
    assert ejercicios[1] == {"caracter": "学", "tipo": "significado", "dificultad": 3, "es_refuerzo": False}


def test_rechaza_nivel_bloqueado_con_el_mensaje_de_v1():
    builder = (
        SesionEstudioBuilder()
        .para_usuario(uuid.uuid4(), nivel_max_desbloqueado=2)
        .en_nivel(5)
        .con_dificultad(3)
        .agregar_contenido_nuevo(["学", "校", "老"])
    )

    with pytest.raises(NivelNoPermitidoError) as error:
        builder.build(RepositorioEspia())
    assert str(error.value) == "HSK5 aún no está desbloqueado (máximo actual: HSK2)."


@pytest.mark.parametrize("ajuste, mensaje", [
    (lambda b: b.para_usuario(None, 3), "requiere un usuario"),
    (lambda b: b.en_nivel(7), "Nivel HSK inválido"),
    (lambda b: b.agregar_contenido_nuevo(["人"] * MAX_EJERCICIOS), "no puede exceder"),
])
def test_validaciones(ajuste, mensaje):
    builder = builder_valido().agregar_contenido_nuevo(["学", "校", "老"])
    ajuste(builder)

    with pytest.raises(SesionInvalidaError, match=mensaje):
        builder.build(RepositorioEspia())


def test_sin_dificultad_no_se_guarda():
    builder = (
        SesionEstudioBuilder()
        .para_usuario(uuid.uuid4(), 3)
        .en_nivel(1)
        .agregar_contenido_nuevo(["学", "校", "老"])
    )

    with pytest.raises(SesionInvalidaError, match="dificultad"):
        builder.build(RepositorioEspia())


def test_la_dificultad_se_acota_entre_1_y_5():
    repo = RepositorioEspia()
    builder_valido().con_dificultad(9).agregar_contenido_nuevo(["学", "校", "老"]).build(repo)
    builder_valido().con_dificultad(-2).agregar_contenido_nuevo(["学", "校", "老"]).build(repo)

    assert [datos["dificultad"] for datos, _ in repo.guardados] == [5, 1]


# ---------- ciclo de vida ----------


def test_cerrar_si_completa():
    sesion = Sesion(ejercicios=[Ej(True), Ej(False)])
    assert reglas.ejercicios_pendientes(sesion) == 1
    assert not reglas.cerrar_si_completa(sesion)

    sesion.ejercicios[1].respondido = True
    assert reglas.cerrar_si_completa(sesion)
    assert sesion.estado == "completada"
    # Una sesión ya cerrada no se vuelve a cerrar.
    assert not reglas.cerrar_si_completa(sesion)


# ---------- repaso ----------


def test_proximo_repaso_como_progreso_flask():
    assert calcular_proximo_repaso(0, True, AHORA) == AHORA + timedelta(days=1)
    assert calcular_proximo_repaso(2, True, AHORA) == AHORA + timedelta(days=7)
    assert calcular_proximo_repaso(99, True, AHORA) == AHORA + timedelta(days=90)
    assert calcular_proximo_repaso(5, False, AHORA) == AHORA + timedelta(hours=12)


def test_racha_previa_desde_la_respuesta_de_progreso():
    assert racha_previa(1, acerto=True) == 0
    assert racha_previa(3, acerto=True) == 2
    assert racha_previa(0, acerto=False) == 0
