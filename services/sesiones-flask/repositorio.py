"""Acceso a la base propia de sesiones y ejercicios."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from modelos import Ejercicio, SesionEstudio


class SesionesRepositorio:
    def __init__(self, sesion_db):
        self._db = sesion_db

    def guardar_sesion(self, datos, ejercicios):
        """Guarda la sesión y sus ejercicios en una sola transacción (lo usa el Builder)."""
        sesion = SesionEstudio(**datos)
        sesion.ejercicios = [Ejercicio(**e) for e in ejercicios]
        self._db.add(sesion)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return sesion

    def obtener_sesion(self, sesion_id):
        return self._db.scalars(
            select(SesionEstudio)
            .where(SesionEstudio.id == sesion_id)
            .options(selectinload(SesionEstudio.ejercicios))
        ).first()

    def obtener_ejercicio_para_responder(self, ejercicio_id):
        """Bloquea la fila (en PostgreSQL) para que no se responda dos veces a la vez."""
        return self._db.scalars(
            select(Ejercicio).where(Ejercicio.id == ejercicio_id).with_for_update()
        ).first()
