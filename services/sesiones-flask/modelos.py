"""Modelos SQLAlchemy de las sesiones de estudio.

Versión SQLAlchemy de services/agente-tutor/tutor/models.py, con los mismos
campos y defaults. `usuario_id` es un UUID suelto, no una clave foránea: los
usuarios viven en otro servicio. Los ejercicios se ordenan por id, que es el
orden en que el Builder los agrega (primero los refuerzos).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from db import Base
from dominio.desempeno import calcular_desempeno

ESTADOS = {
    "borrador": "Borrador",
    "activa": "Activa",
    "completada": "Completada",
}

TIPOS_EJERCICIO = {
    "trazo": "Orden de trazos",
    "pinyin": "Reconocer pinyin",
    "significado": "Significado",
}


def ahora():
    return datetime.now(timezone.utc)


class FechaUTC(TypeDecorator):
    """DateTime que siempre devuelve fechas con zona UTC (SQLite no la guarda)."""

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


class SesionEstudio(Base):
    """Sesión de práctica generada para un usuario en un momento dado.

    Solo persistencia: las reglas de cuándo se cierra o cuántos ejercicios
    quedan pendientes viven en dominio/sesion.py, y las del desempeño en
    dominio/desempeno.py.
    """

    __tablename__ = "sesiones"
    __table_args__ = (
        CheckConstraint("nivel_hsk >= 0", name="ck_sesion_nivel_positivo"),
        CheckConstraint("dificultad >= 0", name="ck_sesion_dificultad_positiva"),
        CheckConstraint("duracion_estimada_min >= 0", name="ck_sesion_duracion_positiva"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    nivel_hsk: Mapped[int] = mapped_column(SmallInteger)
    dificultad: Mapped[int] = mapped_column(SmallInteger)
    estado: Mapped[str] = mapped_column(String(20), default="borrador")
    creada_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora)
    duracion_estimada_min: Mapped[int] = mapped_column(SmallInteger, default=10)
    # RF-IA-05. Desempeño registrado al cerrar la sesión (dominio/desempeno.py).
    # NULL mientras está en curso y en las sesiones cerradas antes de RF-IA-05.
    # Lo agrega migraciones.py en una base que ya existía. duracion_seg y
    # aciertos son para consultas directas a la base: calcular_desempeno()
    # los vuelve a contar desde los ejercicios.
    completada_en: Mapped[datetime | None] = mapped_column(FechaUTC)
    duracion_seg: Mapped[int | None] = mapped_column(Integer)
    aciertos: Mapped[int | None] = mapped_column(SmallInteger)

    ejercicios: Mapped[list["Ejercicio"]] = relationship(
        back_populates="sesion",
        order_by="Ejercicio.id",
        cascade="all, delete-orphan",
    )

    def calcular_desempeno(self):
        """calcularDesempeño() de RF-IA-05: duración, fecha y resultados de la
        sesión terminada, o None si sigue en curso. La regla vive en
        dominio/desempeno.py."""
        return calcular_desempeno(self)

    def __repr__(self):
        return f"Sesión {self.id} usuario {self.usuario_id} HSK{self.nivel_hsk}"


class Ejercicio(Base):
    """Ejercicio individual dentro de una sesión."""

    __tablename__ = "ejercicios"
    __table_args__ = (
        CheckConstraint("dificultad >= 0", name="ck_ejercicio_dificultad_positiva"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sesion_id: Mapped[int] = mapped_column(
        ForeignKey("sesiones.id", ondelete="CASCADE"), index=True
    )
    caracter: Mapped[str] = mapped_column(String(8))
    tipo: Mapped[str] = mapped_column(String(20))
    dificultad: Mapped[int] = mapped_column(SmallInteger)
    # True si nace de un error previo del usuario, no de contenido nuevo.
    es_refuerzo: Mapped[bool] = mapped_column(Boolean, default=False)

    respondido: Mapped[bool] = mapped_column(Boolean, default=False)
    fue_correcto: Mapped[bool | None] = mapped_column(Boolean)
    respondido_en: Mapped[datetime | None] = mapped_column(FechaUTC)
    # RF-IA-02. Tipo de error de un fallo (dominio/codigos_error.py); NULL
    # si acertó o si el fallo no trae código. Lo agrega migraciones.py en
    # una base que ya existía.
    codigo_error: Mapped[str | None] = mapped_column(String(40))
    # RF-IA-03. Patrón de error que originó un ejercicio adaptado
    # (dominio/adaptacion.py); NULL en el resto. Lo agrega migraciones.py.
    patron: Mapped[str | None] = mapped_column(String(40))

    sesion: Mapped[SesionEstudio] = relationship(back_populates="ejercicios")

    def __repr__(self):
        return f"{self.caracter} ({self.tipo})"
