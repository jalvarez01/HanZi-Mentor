"""Modelos SQLAlchemy del catálogo.

Son la versión SQLAlchemy de los modelos Django de services/contenido
(caracteres/models.py y lecciones/models.py), con los mismos campos y
relaciones. Django define el orden por defecto en `Meta.ordering`;
SQLAlchemy no tiene ese concepto, así que el mismo orden queda en las
constantes ORDEN_* (para las consultas) y en `order_by` de las relaciones.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base

TIPOS_EJERCICIO = {
    "trazo": "Orden de trazos",
    "significado": "Significado",
}


def _ahora():
    return datetime.now(timezone.utc)


class Caracter(Base):
    """Un hanzi con su información de escritura y significado."""

    __tablename__ = "caracteres"
    __table_args__ = (
        CheckConstraint("nivel_hsk >= 0", name="ck_caracter_nivel_positivo"),
        CheckConstraint("frecuencia >= 0", name="ck_caracter_frecuencia_positiva"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hanzi: Mapped[str] = mapped_column(String(4), unique=True, index=True)
    pinyin: Mapped[str] = mapped_column(String(64), default="")
    definicion: Mapped[str] = mapped_column(Text, default="")
    radical: Mapped[str] = mapped_column(String(4), default="")
    descomposicion: Mapped[str] = mapped_column(String(64), default="")
    # Null si el carácter no está en ninguna lista oficial.
    nivel_hsk: Mapped[int | None] = mapped_column(SmallInteger, index=True)
    # Posición en listas de frecuencia. Menor = más común.
    frecuencia: Mapped[int | None] = mapped_column(Integer)

    trazos: Mapped[list["Trazo"]] = relationship(
        back_populates="caracter",
        order_by="Trazo.secuencia",
        cascade="all, delete-orphan",
    )
    ejercicios: Mapped[list["Ejercicio"]] = relationship(
        back_populates="caracter",
        cascade="all, delete-orphan",
    )

    def total_trazos(self):
        return len(self.trazos)

    def __repr__(self):
        return f"{self.hanzi} ({self.pinyin})"


class Trazo(Base):
    """Un trazo individual, en su posición dentro del orden de escritura."""

    __tablename__ = "trazos"
    __table_args__ = (
        UniqueConstraint("caracter_id", "secuencia", name="uq_trazo_caracter_secuencia"),
        CheckConstraint("secuencia >= 0", name="ck_trazo_secuencia_positiva"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    caracter_id: Mapped[int] = mapped_column(
        ForeignKey("caracteres.id", ondelete="CASCADE"), index=True
    )
    # Orden de escritura, empezando en 1.
    secuencia: Mapped[int] = mapped_column(SmallInteger)
    # Contorno del trazo. Sistema de 1024x1024 con eje Y invertido.
    path_svg: Mapped[str] = mapped_column(Text)
    # Puntos de la línea central. trazos-flask la compara con el trazo del usuario.
    mediana: Mapped[list] = mapped_column(JSON, default=list)

    caracter: Mapped[Caracter] = relationship(back_populates="trazos")

    def __repr__(self):
        return f"{self.caracter.hanzi} trazo {self.secuencia}"


class Leccion(Base):
    """Agrupa un conjunto de Ejercicios generados para un nivel HSK."""

    __tablename__ = "lecciones"
    __table_args__ = (
        CheckConstraint("nivel_hsk >= 0", name="ck_leccion_nivel_positivo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    nivel_hsk: Mapped[int] = mapped_column(SmallInteger)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)

    ejercicios: Mapped[list["Ejercicio"]] = relationship(
        back_populates="leccion",
        order_by="Ejercicio.id",
        cascade="all, delete-orphan",
    )

    def generarContenido(self, sesion, cantidad=10, excluir=None):
        """RF-APR-02: la entidad ejecuta generarContenido(). La orquestación
        vive en servicio.generar_contenido; esto es solo un delegado."""
        from servicio import generar_contenido

        return generar_contenido(sesion, self, cantidad=cantidad, excluir=excluir)

    def __repr__(self):
        return f"Lección HSK{self.nivel_hsk} usuario {self.usuario_id}"


class Ejercicio(Base):
    """Un ejercicio individual dentro de una Leccion, sobre un Caracter."""

    __tablename__ = "ejercicios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    leccion_id: Mapped[int] = mapped_column(
        ForeignKey("lecciones.id", ondelete="CASCADE"), index=True
    )
    caracter_id: Mapped[int] = mapped_column(
        ForeignKey("caracteres.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(16))
    completado: Mapped[bool] = mapped_column(Boolean, default=False)

    leccion: Mapped[Leccion] = relationship(back_populates="ejercicios")
    caracter: Mapped[Caracter] = relationship(back_populates="ejercicios")

    def __repr__(self):
        return f"{TIPOS_EJERCICIO.get(self.tipo, self.tipo)} {self.caracter.hanzi}"


# Orden por defecto de las consultas (Meta.ordering en Django). En PostgreSQL
# los NULL van al final en orden ascendente; se deja explícito para que
# SQLite ordene igual.
ORDEN_CARACTERES = (
    Caracter.nivel_hsk.asc().nulls_last(),
    Caracter.frecuencia.asc().nulls_last(),
    Caracter.hanzi.asc(),
)
ORDEN_LECCIONES = (Leccion.creada_en.desc(),)
