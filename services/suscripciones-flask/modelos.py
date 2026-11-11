"""Modelos SQLAlchemy: la entidad Suscripcion y su historial de pagos.

`usuario_id` es un UUID suelto, no una clave foránea: los usuarios viven en
otro servicio (igual que en progreso-flask y sesiones-flask).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime, TypeDecorator

from db import Base
from dominio.suscripcion import ahora


class FechaUTC(TypeDecorator):
    """DateTime que siempre devuelve fechas con zona UTC.

    SQLite no guarda la zona horaria; sin esto, comparar `vence_en` con la
    hora actual fallaría al releer (igual que en progreso-flask).
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


class Suscripcion(Base):
    """Una fila por usuario que alguna vez pagó Premium.

    Un usuario sin fila tiene Free. `estado` guarda solo activa o cancelada:
    vencida se calcula con `vence_en` (ver dominio/suscripcion.py).
    """

    __tablename__ = "suscripciones"
    __table_args__ = (
        CheckConstraint("plan IN ('free', 'premium')", name="ck_suscripcion_plan"),
        CheckConstraint("estado IN ('activa', 'cancelada')", name="ck_suscripcion_estado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True)
    plan: Mapped[str] = mapped_column(String(10))
    estado: Mapped[str] = mapped_column(String(10))
    # Inicio del periodo pagado más reciente.
    inicio: Mapped[datetime] = mapped_column(FechaUTC)
    vence_en: Mapped[datetime] = mapped_column(FechaUTC)
    cancelada_en: Mapped[datetime | None] = mapped_column(FechaUTC, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora)
    actualizada_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora, onupdate=ahora)


class Pago(Base):
    """Cada intento de cobro que la pasarela respondió, aprobado o rechazado.

    De la tarjeta solo se guardan la marca y los últimos 4 dígitos.
    """

    __tablename__ = "pagos"
    __table_args__ = (
        CheckConstraint("estado IN ('aprobado', 'rechazado')", name="ck_pago_estado"),
        CheckConstraint("monto >= 0", name="ck_pago_monto"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    # Null si se rechazó la activación: todavía no había suscripción.
    suscripcion_id: Mapped[int | None] = mapped_column(
        ForeignKey("suscripciones.id"), nullable=True
    )
    concepto: Mapped[str] = mapped_column(String(12))
    monto: Mapped[int] = mapped_column(Integer)
    moneda: Mapped[str] = mapped_column(String(3))
    estado: Mapped[str] = mapped_column(String(10))
    # Código de la pasarela si se rechazó (TARJETA_RECHAZADA...).
    codigo_rechazo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    referencia: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pasarela: Mapped[str] = mapped_column(String(20))
    marca: Mapped[str] = mapped_column(String(12))
    ultimos4: Mapped[str] = mapped_column(String(4))
    creado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora)
