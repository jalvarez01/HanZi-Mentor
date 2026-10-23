"""Valida la forma de la entrada antes de llegar al servicio.

Reemplaza a los serializers de entrada de DRF. Cada error se lanza como
ErrorDominio con 400 y código ENTRADA_INVALIDA.
"""

import uuid

from errores import ErrorDominio

LIMITE_DEFECTO = 20
LIMITE_MAXIMO = 100

NIVEL_MINIMO = 1
NIVEL_MAXIMO = 6
CANTIDAD_DEFECTO = 10
CANTIDAD_MAXIMA = 50


def _invalida(mensaje):
    return ErrorDominio(mensaje, "ENTRADA_INVALIDA")


def _entero_de_texto(texto):
    """int de un parámetro de la URL, o None si no es un entero."""
    texto = texto.strip()
    if texto.startswith("-"):
        return -int(texto[1:]) if texto[1:].isdigit() else None
    return int(texto) if texto.isdigit() else None


def validar_consulta_caracteres(argumentos):
    """Devuelve (nivel, excluir, limite) de GET /api/v2/caracteres/.

    En v1 un `limite` no numérico o negativo respondía 500; acá es 400.
    """
    nivel = None
    texto_nivel = argumentos.get("nivel", "")
    if texto_nivel:
        nivel = _entero_de_texto(texto_nivel)
        if nivel is None:
            raise _invalida("El nivel debe ser un número entero")

    limite = LIMITE_DEFECTO
    texto_limite = argumentos.get("limite")
    if texto_limite is not None:
        limite = _entero_de_texto(texto_limite)
        if limite is None or not 1 <= limite <= LIMITE_MAXIMO:
            raise _invalida(f"El límite debe ser un entero entre 1 y {LIMITE_MAXIMO}")

    excluir = [c for c in argumentos.get("excluir", "").split(",") if c]
    return nivel, excluir, limite


def _entero_de_json(valor):
    """Como IntegerField de DRF: acepta 3 y "3", no True ni 3.5."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    if isinstance(valor, str):
        return _entero_de_texto(valor) if valor.strip() else None
    return None


def _uuid_de_json(valor):
    """Como UUIDField de DRF: acepta el texto del UUID o un entero."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        try:
            return uuid.UUID(int=valor)
        except ValueError:
            return None
    if isinstance(valor, str):
        try:
            return uuid.UUID(valor)
        except ValueError:
            return None
    return None


def _entero_en_rango(datos, campo, minimo, maximo, defecto=None):
    if campo not in datos:
        if defecto is None:
            raise _invalida(f"El campo '{campo}' es obligatorio")
        return defecto

    valor = _entero_de_json(datos[campo])
    if valor is None or not minimo <= valor <= maximo:
        raise _invalida(f"El campo '{campo}' debe ser un entero entre {minimo} y {maximo}")
    return valor


def validar_generar_leccion(datos):
    """Devuelve (usuario_id, nivel_hsk, cantidad) de POST /api/v2/lecciones/generar/."""
    if not isinstance(datos, dict):
        raise _invalida("El cuerpo debe ser un objeto JSON")

    if "usuario_id" not in datos:
        raise _invalida("El campo 'usuario_id' es obligatorio")
    usuario_id = _uuid_de_json(datos["usuario_id"])
    if usuario_id is None:
        raise _invalida("El campo 'usuario_id' debe ser un UUID válido")

    nivel_hsk = _entero_en_rango(datos, "nivel_hsk", NIVEL_MINIMO, NIVEL_MAXIMO)
    cantidad = _entero_en_rango(
        datos, "cantidad", 1, CANTIDAD_MAXIMA, defecto=CANTIDAD_DEFECTO
    )
    return usuario_id, nivel_hsk, cantidad
