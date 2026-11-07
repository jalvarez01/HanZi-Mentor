"""Arma el JSON de la respuesta de evaluación.

Para trazo, los campos del veredicto van en el orden de
ResultadoComparacionSerializer de contenido v1 (tests/test_contrato.py lo
comprueba). trazos-flask no devuelve `distancia_media`, y `razon_longitud`
solo lo usa el explicador: ninguno de los dos aparece.

Al final, y solo cuando corresponde (RF-IA-04):
- `nota` {codigo, texto} si la respuesta acierta: el tono de un pinyin o
  el tramo a mejorar de un trazo aprobado;
- `explicacion` {codigo, titulo, porque, pista} si `acerto` es false.
Los textos salen en el idioma de la petición; `codigo` no cambia.
"""

from dominio.explicacion import Fragmento
from i18n import traducir

CAMPOS_TRAZO = ("aprobado", "puntaje", "motivo", "invertido", "detalle", "puntos_lejanos")


def _params(params):
    # Primero se traducen las partes de la frase ("hacia abajo"), después la frase.
    return {k: traducir(v) if isinstance(v, Fragmento) else v for k, v in params.items()}


def explicacion(e):
    params = _params(e.params)
    return {
        "codigo": e.codigo,
        "titulo": traducir(e.titulo, params),
        "porque": traducir(e.porque, params),
        "pista": traducir(e.pista, params),
    }


def nota(n):
    return {"codigo": n.codigo, "texto": traducir(n.texto, _params(n.params))}


def resultado(r):
    datos = {"tipo": r.tipo, "caracter": r.caracter, "acerto": r.acerto}
    if r.tipo == "trazo":
        datos["secuencia"] = r.secuencia
        for campo in CAMPOS_TRAZO:
            if campo in r.detalle_trazo:
                datos[campo] = r.detalle_trazo[campo]
    if r.nota is not None and r.acerto:
        datos["nota"] = nota(r.nota)
    if r.explicacion is not None and not r.acerto:
        datos["explicacion"] = explicacion(r.explicacion)
    return datos
