"""Notas para respuestas correctas (RF-IA-04). No cambian `acerto`.

- PINYIN_TONO: el tono no se evalúa (dominio/evaluacion.py), así que "hao"
  acierta para 好. La nota dice cómo se lee de verdad: "Se lee hǎo, tercer
  tono."
- TRAZO_MEJORA: un trazo aprobado como "aceptable" que se desvió en un
  tramo. La nota dice dónde y, si en ese tramo el trazo cambia de
  dirección, hacia dónde: "Bien. Al final, el trazo gira hacia la derecha."
"""

from dominio.evaluacion import lectura_que_coincide
from dominio.explicacion import Fragmento, Nota
from dominio.geometria import direccion_general, direccion_local, mediana_de, parte
from dominio.pinyin import tono
from mensajes import N_

NOMBRES_TONO = {
    0: Fragmento(N_("tono neutro")),
    1: Fragmento(N_("primer tono")),
    2: Fragmento(N_("segundo tono")),
    3: Fragmento(N_("tercer tono")),
    4: Fragmento(N_("cuarto tono")),
}


def nota_de_tono(respuesta_usuario, datos_correctos):
    """La nota PINYIN_TONO con la lectura que coincidió, o None si no acertó."""
    lectura = lectura_que_coincide(respuesta_usuario, datos_correctos)
    if lectura is None:
        return None
    return Nota(
        "PINYIN_TONO",
        N_("Se lee %(lectura)s, %(tono)s."),
        {"lectura": lectura, "tono": NOMBRES_TONO[tono(lectura)]},
    )


# En ese tramo el trazo va en otra dirección que de punta a punta: gira.
GIRA = {
    "principio": N_("Bien. Al principio, el trazo sale %(direccion)s."),
    "medio": N_("Bien. En el medio, el trazo gira %(direccion)s."),
    "final": N_("Bien. Al final, el trazo gira %(direccion)s."),
}
# Misma dirección: solo se alejó de la guía.
AJUSTA = {
    "principio": N_("Bien. Al principio, seguí más cerca de la guía."),
    "medio": N_("Bien. En el medio, seguí más cerca de la guía."),
    "final": N_("Bien. Al final, seguí más cerca de la guía."),
}


def nota_de_mejora(datos_correctos, secuencia, veredicto):
    """La nota TRAZO_MEJORA de un trazo aprobado con `puntos_lejanos`, o None.

    El tramo sale del punto con mayor desvío. La dirección local se calcula
    con la mediana en ese tramo y se compara con la de punta a punta.
    """
    if not veredicto.get("aprobado"):
        return None
    lejanos = [
        p for p in veredicto.get("puntos_lejanos") or []
        if isinstance(p, dict) and isinstance(p.get("posicion"), (int, float))
    ]
    mediana = mediana_de(datos_correctos, secuencia)
    if not lejanos or mediana is None:
        return None

    posicion = max(lejanos, key=lambda p: p.get("desvio") or 0)["posicion"]
    donde = parte(posicion)
    local = direccion_local(mediana, posicion)
    if local != direccion_general(mediana):
        return Nota("TRAZO_MEJORA", GIRA[donde], {"direccion": local})
    return Nota("TRAZO_MEJORA", AJUSTA[donde])
