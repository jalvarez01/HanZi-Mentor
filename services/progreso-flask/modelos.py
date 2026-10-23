"""Modelo SQLAlchemy del progreso.

Versión SQLAlchemy de services/agente-tutor/progreso/models.py, con los
mismos campos y defaults. `usuario_id` es un UUID suelto, no una clave
foránea: los usuarios viven en otro servicio.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, Integer, SmallInteger, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from db import Base
from dominio import progreso as reglas
from dominio.repaso import ahora


class FechaUTC(TypeDecorator):
    """DateTime que siempre devuelve fechas con zona UTC.

    SQLite no guarda la zona horaria y devuelve fechas sin ella; sin esto,
    comparar `proximo_repaso` con una fecha nueva fallaría al releer.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, valor, dialecto):
        if valor is not None and valor.tzinfo is not None:
            valor = valor.astimezone(timezone.utc)
        return valor

    def process_result_value(self, valor, dialecto):
        if valor is None:
            return None
        if valor.tzinfo is None:
            return valor.replace(tzinfo=timezone.utc)
        return valor.astimezone(timezone.utc)


class ProgresoUsuario(Base):
    """Estado de aprendizaje de un usuario: qué domina, qué falla, hasta dónde llegó.

    Las reglas que deciden cómo cambia este estado viven en dominio/. Los
    métodos registrar_* son atajos a esas reglas y no guardan nada.
    """

    __tablename__ = "progresos"
    __table_args__ = (
        CheckConstraint("nivel_hsk >= 0", name="ck_progreso_nivel_positivo"),
        CheckConstraint("nivel_max_desbloqueado >= 0", name="ck_progreso_nivel_max_positivo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True)

    # Nivel en el que está practicando actualmente.
    nivel_hsk: Mapped[int] = mapped_column(SmallInteger, default=1)
    # Nivel más alto al que tiene acceso.
    nivel_max_desbloqueado: Mapped[int] = mapped_column(SmallInteger, default=1)
    # Proporción de respuestas correctas, de 0.0 a 1.0.
    tasa_acierto: Mapped[float] = mapped_column(Float, default=0.5)

    # Caracteres que ya no necesitan repaso frecuente.
    caracteres_dominados: Mapped[list] = mapped_column(JSON, default=list)
    # Carácter -> número de veces que se falló.
    errores_frecuentes: Mapped[dict] = mapped_column(JSON, default=dict)
    # Carácter -> aciertos seguidos. Alimenta el repaso espaciado.
    aciertos_consecutivos: Mapped[dict] = mapped_column(JSON, default=dict)
    # Carácter -> fecha ISO del próximo repaso.
    agenda_repaso: Mapped[dict] = mapped_column(JSON, default=dict)

    # El más cercano de la agenda. Permite consultar sin abrir el JSON.
    proximo_repaso: Mapped[datetime | None] = mapped_column(FechaUTC)
    # Como auto_now de Django: se actualiza en cada guardado.
    actualizado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora, onupdate=ahora)

    def __init__(self, **campos):
        # Los defaults de mapped_column se aplican al insertar; acá se ponen
        # desde el principio para que las reglas trabajen con la entidad nueva.
        campos.setdefault("nivel_hsk", 1)
        campos.setdefault("nivel_max_desbloqueado", 1)
        campos.setdefault("tasa_acierto", 0.5)
        campos.setdefault("caracteres_dominados", [])
        campos.setdefault("errores_frecuentes", {})
        campos.setdefault("aciertos_consecutivos", {})
        campos.setdefault("agenda_repaso", {})
        super().__init__(**campos)

    def registrar_error(self, caracter):
        reglas.registrar_error(self, caracter)

    def registrar_acierto(self, caracter):
        reglas.registrar_acierto(self, caracter)

    def __repr__(self):
        return f"Progreso de {self.usuario_id} HSK{self.nivel_hsk}"
