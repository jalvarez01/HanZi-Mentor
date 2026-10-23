"""Casos de uso del catálogo: consultan la base y delegan en el dominio.

Port de las vistas y de LeccionService de services/contenido. La validación
de trazos no está acá: vive en services/trazos-flask.
"""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from dominio.lecciones import LeccionBuilder
from errores import ErrorDominio
from modelos import ORDEN_CARACTERES, Caracter, Ejercicio, Leccion


def listar_caracteres(sesion, nivel=None, excluir=None, limite=20):
    consulta = select(Caracter).order_by(*ORDEN_CARACTERES)
    if nivel is not None:
        consulta = consulta.where(Caracter.nivel_hsk == nivel)
    if excluir:
        consulta = consulta.where(Caracter.hanzi.not_in(excluir))
    return list(sesion.scalars(consulta.limit(limite)))


def obtener_caracter(sesion, hanzi):
    caracter = sesion.scalars(
        select(Caracter)
        .where(Caracter.hanzi == hanzi)
        .options(selectinload(Caracter.trazos))
    ).first()
    if caracter is None:
        raise ErrorDominio("Carácter no encontrado.", "NO_ENCONTRADO", estado=404)
    return caracter


def generar_contenido(sesion, leccion, cantidad=10, excluir=None, aleatorio=None):
    """Crea los ejercicios de la lección. No hace commit: lo decide quien llama."""
    excluir = excluir or []

    def candidatos(condicion):
        consulta = select(Caracter).where(condicion)
        if excluir:
            consulta = consulta.where(Caracter.hanzi.not_in(excluir))
        return list(sesion.scalars(consulta.order_by(Caracter.id)))

    planes = (
        LeccionBuilder(aleatorio)
        .con_caracteres_del_nivel(
            del_nivel=candidatos(Caracter.nivel_hsk == leccion.nivel_hsk),
            sin_clasificar=candidatos(Caracter.nivel_hsk.is_(None)),
            cantidad=cantidad,
        )
        .con_ejercicios_variados()
        .build()
    )

    ejercicios = [
        Ejercicio(leccion=leccion, caracter=plan.caracter, tipo=plan.tipo)
        for plan in planes
    ]
    sesion.add_all(ejercicios)
    sesion.flush()
    return ejercicios


def generar_leccion(sesion, usuario_id, nivel_hsk, cantidad=10):
    """POST /lecciones/generar/: crea la lección y su contenido en una transacción."""
    leccion = Leccion(usuario_id=usuario_id, nivel_hsk=nivel_hsk)
    sesion.add(leccion)
    try:
        leccion.generarContenido(sesion, cantidad=cantidad)
        sesion.commit()
    except Exception:
        sesion.rollback()
        raise
    return leccion


def obtener_leccion(sesion, leccion_id):
    leccion = sesion.scalars(
        select(Leccion)
        .where(Leccion.id == leccion_id)
        .options(selectinload(Leccion.ejercicios).selectinload(Ejercicio.caracter))
    ).first()
    if leccion is None:
        raise ErrorDominio("Lección no encontrada.", "NO_ENCONTRADO", estado=404)
    return leccion
