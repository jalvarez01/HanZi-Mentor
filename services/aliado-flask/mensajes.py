"""Marca de textos traducibles para el código que no importa Flask (T22).

`N_` no traduce nada: devuelve el texto tal cual, en español, y le avisa a
pybabel que lo extraiga. La traducción se hace al responder, con
`i18n.traducir()`.
"""


def N_(texto):
    return texto
