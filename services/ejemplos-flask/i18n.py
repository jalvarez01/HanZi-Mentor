"""Idioma de las respuestas con Flask-Babel (T22).

La cabecera Accept-Language de cada petición elige entre español e inglés.
Sin cabecera, o con un idioma que no está, se responde en español.

Solo se traduce el texto para personas (`error`, `detalle`, `aviso`). Las
claves del JSON, los códigos (`codigo`) y los estados HTTP no cambian.

El dominio no importa Flask: marca sus textos con `mensajes.N_` y los deja
en español; se traducen acá, en el borde HTTP, con `traducir()`. Los
textos con datos usan marcadores con nombre (`%(nivel)s`), así la frase se
puede reordenar en cada idioma.
"""

from pathlib import Path

from flask import has_request_context, request
from flask_babel import Babel, gettext

IDIOMAS = ("es", "en")
IDIOMA_POR_DEFECTO = "es"
TRADUCCIONES = Path(__file__).resolve().parent / "translations"


def elegir_idioma():
    if not has_request_context():
        return IDIOMA_POR_DEFECTO
    return request.accept_languages.best_match(IDIOMAS, default=IDIOMA_POR_DEFECTO)


def iniciar_i18n(app):
    app.config.setdefault("BABEL_DEFAULT_LOCALE", IDIOMA_POR_DEFECTO)
    app.config.setdefault("BABEL_TRANSLATION_DIRECTORIES", str(TRADUCCIONES))
    Babel(app, locale_selector=elegir_idioma)


def traducir(texto, params=None):
    """Traduce un texto marcado con N_ al idioma de la petición.

    Un texto vacío se devuelve igual: gettext("") daría la cabecera del .po.
    """
    if not texto:
        return texto
    return gettext(texto, **params) if params else gettext(texto)


def compilar_traducciones(carpeta=TRADUCCIONES):
    """Compila cada .po a .mo. Lo usan las pruebas; Docker usa pybabel compile."""
    from babel.messages.mofile import write_mo
    from babel.messages.pofile import read_po

    for po in Path(carpeta).glob("*/LC_MESSAGES/messages.po"):
        with po.open("rb") as entrada:
            catalogo = read_po(entrada)
        with po.with_suffix(".mo").open("wb") as salida:
            write_mo(salida, catalogo)
