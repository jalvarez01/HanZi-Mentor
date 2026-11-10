"""Adaptador "reglas": explica los errores con reglas fijas, sin red ni azar.

Solo usa datos que ya existen: el veredicto de trazos-flask, la mediana del
trazo en el catálogo, las lecturas con tono y la definición. La misma
entrada da siempre la misma explicación, así las pruebas comparan textos.

El bloque se muestra debajo del veredicto (en Trazos, el detalle de
trazos-flask; en Práctica, el aviso de fallo y la respuesta correcta), así
que no lo repite:
- titulo: dónde o qué parte, corto;
- porque: una sola idea (por qué importa o la causa probable), con
  palabras cotidianas y sin metáforas: dos frases cortas como mucho;
- pista: una acción concreta con los datos reales. En pinyin no repite la
  lectura que Práctica ya muestra: dice cómo pronunciarla.

Trazo: la dirección y las zonas se calculan con el primer y el último punto
de la mediana (dominio/geometria.py). En trazos con giro es una
aproximación: describe el recorrido de punta a punta.
"""

import re

from dominio.evaluacion import (
    es_sentido_corto,
    lecturas,
    sentido_mas_parecido,
    sentidos,
    similitud_significado,
    umbral_significado,
)
from dominio.explicacion import Explicacion
from dominio.geometria import direccion, mediana_de, tramo, zona
from dominio.notas import NOMBRES_TONO
from dominio.pinyin import base, separar, sin_tono, tono
from dominio.puertos import ExplicadorErrores
from mensajes import N_

# --- Significado -------------------------------------------------------------

# Palabras que no cuentan como acierto parcial aunque estén en la definición.
PALABRAS_VACIAS = {"a", "an", "the", "to", "of", "in", "on", "at", "and", "or", "be"}

# Debajo del umbral, a esta distancia o menos, la respuesta es "cercana".
MARGEN_CERCANO = 0.15


def _palabras(texto):
    return re.findall(r"[^\W\d_]+", (texto or "").lower())


class ExplicadorReglas(ExplicadorErrores):
    nombre = "reglas"

    def explicar_error(self, tipo, error):
        if error.acerto:
            return None
        if tipo == "trazo":
            return self._trazo(error)
        if tipo == "pinyin":
            return self._pinyin(error)
        if tipo == "significado":
            return self._significado(error)
        return None

    # ------------------------------------------------------------------ trazo

    def _trazo(self, error):
        veredicto = error.veredicto_trazo or {}
        mediana = mediana_de(error.datos_correctos, error.secuencia)
        if mediana is None:
            return None

        inicio, fin = mediana[0], mediana[-1]
        params = {
            "secuencia": error.secuencia,
            "inicio": zona(inicio),
            "fin": zona(fin),
            "direccion": direccion(inicio, fin),
        }
        motivo = veredicto.get("motivo")

        if motivo == "fuera_de_lugar":
            # El detalle de arriba ya dice "fuera de lugar": acá, dónde va.
            return Explicacion(
                "TRAZO_FUERA_DE_LUGAR",
                N_("Trazo %(secuencia)s"),
                N_("Cada trazo tiene su lugar dentro del carácter."),
                N_("Empezá %(inicio)s y avanzá %(direccion)s."),
                params,
            )

        if motivo == "invertido":
            return Explicacion(
                "TRAZO_INVERTIDO",
                N_("Trazo %(secuencia)s al revés"),
                N_(
                    "Cada trazo se escribe siempre en el mismo sentido. Así lo "
                    "recordás mejor y escribís más rápido."
                ),
                N_("Empezá %(inicio)s y avanzá %(direccion)s."),
                params,
            )

        if motivo == "incompleto":
            return self._largo(veredicto.get("razon_longitud"), params)

        if motivo == "impreciso":
            lejanos = veredicto.get("puntos_lejanos") or []
            if lejanos and isinstance(lejanos[0].get("posicion"), (int, float)):
                titulo = N_("Trazo %(secuencia)s: desvío %(tramo)s")
                params["tramo"] = tramo(lejanos[0]["posicion"])
            else:
                titulo = N_("Trazo %(secuencia)s: forma")
            return Explicacion(
                "TRAZO_IMPRECISO",
                titulo,
                N_(
                    "Si un trazo se corre de lugar, todo el carácter se deforma."
                ),
                N_("Mirá el modelo: el trazo empieza %(inicio)s y va %(direccion)s."),
                params,
            )

        return None

    @staticmethod
    def _largo(razon, params):
        if not isinstance(razon, (int, float)) or isinstance(razon, bool):
            # Respaldo: un trazos-flask anterior no manda razon_longitud.
            return Explicacion(
                "TRAZO_INCOMPLETO",
                N_("Trazo %(secuencia)s: inicio y final"),
                N_(
                    "Cada trazo tiene un largo fijo. Si cambia, el carácter "
                    "queda deforme."
                ),
                N_("Empezá %(inicio)s y terminá %(fin)s."),
                params,
            )

        params["porcentaje"] = round(razon * 100)
        if razon < 1:
            return Explicacion(
                "TRAZO_CORTO",
                N_("Trazo %(secuencia)s: falta el final"),
                N_(
                    "Llegaste a cerca del %(porcentaje)s %% del trazo. Si no lo "
                    "terminás, el carácter queda deforme."
                ),
                N_("Mantené el dedo apoyado hasta llegar %(fin)s."),
                params,
            )
        return Explicacion(
            "TRAZO_LARGO",
            N_("Trazo %(secuencia)s: sobra recorrido"),
            N_(
                "Mide cerca del %(porcentaje)s %% de lo esperado. Quizá uniste "
                "este trazo con el siguiente; cada uno va por separado."
            ),
            N_("Levantá el dedo cuando llegues %(fin)s."),
            params,
        )

    # ----------------------------------------------------------------- pinyin

    def _pinyin(self, error):
        todas = lecturas(error.datos_correctos)
        escrito = sin_tono(error.respuesta)
        principal = todas[0] if todas else ""
        params = {
            "caracter": error.caracter,
            "lectura": principal,
            "tono": NOMBRES_TONO[tono(principal)],
        }

        # Solo se analiza una sílaba: una respuesta con espacios o vacía es
        # "distinta" sin más detalle.
        if escrito and " " not in escrito:
            inicial_escrita, final_escrita = separar(escrito)
            cercanas = []
            for lectura in todas:
                inicial, final = separar(sin_tono(lectura))
                if not (inicial and inicial_escrita and final and final_escrita):
                    continue
                if base(final) == base(final_escrita) and inicial != inicial_escrita:
                    cercanas.append((0, "PINYIN_INICIAL", lectura, inicial, final))
                elif inicial == inicial_escrita and base(final) != base(final_escrita):
                    cercanas.append((1, "PINYIN_FINAL", lectura, inicial, final))

            if cercanas:
                _, codigo, lectura, inicial, final = min(cercanas, key=lambda c: c[0])
                params.update(lectura=lectura, inicial=inicial, final=final,
                              inicial_escrita=inicial_escrita, final_escrita=final_escrita,
                              tono=NOMBRES_TONO[tono(lectura)])
                # La lectura ya se muestra arriba: la pista dice cómo pronunciarla.
                pista = N_(
                    "Decilo en dos partes, %(inicial)s y %(final)s, y después "
                    "juntalas con el %(tono)s."
                )
                if codigo == "PINYIN_INICIAL":
                    return Explicacion(
                        codigo,
                        N_("Consonante inicial"),
                        N_(
                            "La terminación %(final)s está bien. Con otra letra al "
                            "comienzo, ya es otra palabra."
                        ),
                        pista,
                        params,
                    )
                return Explicacion(
                    codigo,
                    N_("Terminación de la sílaba"),
                    N_(
                        "La consonante %(inicial)s está bien. Con otra terminación, "
                        "ya es otra palabra."
                    ),
                    pista,
                    params,
                )

        if len(todas) > 1:
            params["otras"] = ", ".join(todas[1:])
            pista = N_(
                "Decí la lectura principal en voz alta con el %(tono)s; según la "
                "palabra, también se lee %(otras)s."
            )
        else:
            pista = N_(
                "Mirá el carácter y decí su lectura en voz alta tres veces, "
                "con el %(tono)s."
            )
        return Explicacion(
            "PINYIN_DISTINTO",
            N_("Inicial y terminación"),
            N_(
                "Suele pasar cuando lo confundís con un carácter parecido."
            ),
            pista,
            params,
        )

    # ------------------------------------------------------------ significado

    def _significado(self, error):
        definicion = error.datos_correctos.get("definicion") or ""
        if not definicion.strip():
            return None
        params = {"caracter": error.caracter, "definicion": definicion}

        en_definicion = set(_palabras(definicion)) - PALABRAS_VACIAS
        comunes = [p for p in dict.fromkeys(_palabras(error.respuesta)) if p in en_definicion]
        if comunes:
            sentido = next(s for s in sentidos(definicion) if set(_palabras(s)) & set(comunes))
            params.update(comunes=", ".join(comunes), sentido=sentido)
            return Explicacion(
                "SIGNIFICADO_PARCIAL",
                N_("Sobran palabras"),
                N_(
                    "%(comunes)s está bien, pero las otras palabras no son parte "
                    "del significado."
                ),
                N_("Respondé con un solo sentido, por ejemplo: %(sentido)s."),
                params,
            )

        # "Casi" solo si lo más parecido es un sentido largo: uno corto
        # ("an", "one") exige coincidencia exacta y la ortografía no alcanza.
        similitud = similitud_significado(error.respuesta, definicion)
        cerca = similitud >= umbral_significado(error.dificultad) - MARGEN_CERCANO
        if cerca and not es_sentido_corto(sentido_mas_parecido(error.respuesta, definicion)):
            return Explicacion(
                "SIGNIFICADO_CERCANO",
                N_("Ortografía"),
                N_(
                    "La palabra se parece, pero en esta dificultad tiene que estar "
                    "bien escrita."
                ),
                N_("Compará letra por letra con la definición: %(definicion)s."),
                params,
            )

        # Sin detección de idioma: si escribió en español, cae acá y la pista
        # se lo recuerda.
        return Explicacion(
            "SIGNIFICADO_DISTINTO",
            N_("Otro sentido"),
            N_(
                "Suele pasar cuando lo confundís con un carácter parecido."
            ),
            N_(
                "Definición: %(definicion)s. Respondé en inglés, como aparece "
                "en el catálogo."
            ),
            params,
        )
