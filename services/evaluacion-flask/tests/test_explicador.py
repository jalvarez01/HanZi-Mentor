"""RF-IA-04: explicación de cada error, nota de tono y fábrica del explicador.

El bloque se muestra debajo del veredicto, así que sus textos no lo repiten:
el título dice dónde, el porqué da la causa o por qué importa y la pista,
una acción con datos reales (en pinyin, sin repetir la lectura).

Los textos se comparan enteros: el adaptador "reglas" es determinista. Las
trazas usan la mediana real del trazo 1 de 人, que va de (483, 736) a
(72, 95): empieza arriba al centro y baja hacia la izquierda.
"""

import pytest

from adaptadores.fabrica import crear_explicador
from adaptadores.reglas import ExplicadorReglas, direccion, tramo, zona
from dominio.geometria import direccion_general, direccion_local, punto_en
from app import create_app
from conftest import CatalogoFalso, TrazosFalso
from dominio.explicacion import ErrorEvaluado
from dominio.pinyin import separar, tono
from dominio.puertos import ExplicadorErrores
from fabricas import Dependencias

URL = "/api/v2/evaluacion/"
EN = {"Accept-Language": "en"}

MEDIANA_REN = [[483, 736], [300, 400], [72, 95]]
# Trazo 2 real de 人: baja hacia la derecha y al final se aplana hacia la derecha.
MEDIANA_REN_2 = [[474, 477], [477, 459], [490, 439], [571, 333], [691, 200], [753, 145], [798, 119], [986, 90]]
DETALLES = {
    "人": {
        "hanzi": "人", "pinyin": "rén", "lecturas": ["rén"],
        "definicion": "man, person; people",
        "trazos": [
            {"secuencia": 1, "mediana": MEDIANA_REN},
            {"secuencia": 2, "mediana": MEDIANA_REN_2},
        ],
    },
    "好": {
        "hanzi": "好", "pinyin": "hǎo", "lecturas": ["hǎo", "hào"],
        "definicion": "good, excellent, fine; proper, suitable; well", "trazos": [],
    },
    "长": {"hanzi": "长", "pinyin": "zhǎng", "lecturas": ["zhǎng", "cháng"], "trazos": []},
    "了": {"hanzi": "了", "pinyin": "le", "lecturas": ["le", "liǎo", "liào"], "trazos": []},
    "七": {"hanzi": "七", "pinyin": "qī", "lecturas": ["qī"], "definicion": "seven", "trazos": []},
    "一": {"hanzi": "一", "pinyin": "yī", "lecturas": ["yī"], "definicion": "one; a, an; alone", "trazos": []},
}
TRAZO = {"secuencia": 1, "puntos": [[0, 0], [1, 1]], "ancho": 300, "alto": 300}


def veredicto(motivo, **extra):
    return {
        "aprobado": False, "puntaje": 30, "motivo": motivo, "detalle": "x",
        "invertido": motivo == "invertido", "puntos_lejanos": [], **extra,
    }


def cliente(veredicto_trazo=None, explicador=None):
    deps = Dependencias(
        catalogo=CatalogoFalso(DETALLES),
        trazos=TrazosFalso(veredicto_trazo),
        **({"explicador": explicador} if explicador else {}),
    )
    return create_app({"TESTING": True}, dependencias=deps).test_client()


def evaluar(cuerpo, veredicto_trazo=None, cabeceras=None):
    return cliente(veredicto_trazo).post(URL, json=cuerpo, headers=cabeceras or {}).get_json()


def trazo(v, cabeceras=None, secuencia=1):
    respuesta = {**TRAZO, "secuencia": secuencia}
    return evaluar({"tipo": "trazo", "caracter": "人", "respuesta": respuesta}, v, cabeceras)


def aceptable(*lejanos):
    """Veredicto aprobado como "aceptable", con sus puntos_lejanos."""
    return {
        "aprobado": True, "puntaje": 80, "motivo": "correcto",
        "detalle": "Trazo aceptable. Con más precisión quedaría perfecto.",
        "invertido": False, "puntos_lejanos": list(lejanos),
    }


def pinyin(caracter, respuesta, cabeceras=None):
    return evaluar({"tipo": "pinyin", "caracter": caracter, "respuesta": respuesta}, cabeceras=cabeceras)


def significado(caracter, respuesta, cabeceras=None, dificultad=3):
    cuerpo = {"tipo": "significado", "caracter": caracter, "respuesta": respuesta, "dificultad": dificultad}
    return evaluar(cuerpo, cabeceras=cabeceras)


# ------------------------------------------------------------------ trazo


def test_trazo_invertido():
    datos = trazo(veredicto("invertido"))

    assert datos["explicacion"] == {
        "codigo": "TRAZO_INVERTIDO",
        "titulo": "Trazo 1 al revés",
        "porque": (
            "Cada trazo se escribe siempre en el mismo sentido. Así lo recordás "
            "mejor y escribís más rápido."
        ),
        "pista": "Empezá arriba al centro y avanzá hacia abajo y a la izquierda.",
    }


def test_trazo_fuera_de_lugar():
    datos = trazo(veredicto("fuera_de_lugar"))

    assert datos["explicacion"] == {
        "codigo": "TRAZO_FUERA_DE_LUGAR",
        "titulo": "Trazo 1",
        "porque": "Cada trazo tiene su lugar dentro del carácter.",
        "pista": "Empezá arriba al centro y avanzá hacia abajo y a la izquierda.",
    }


def test_trazo_fuera_de_lugar_en_ingles():
    datos = trazo(veredicto("fuera_de_lugar"), EN)

    assert datos["explicacion"] == {
        "codigo": "TRAZO_FUERA_DE_LUGAR",
        "titulo": "Stroke 1",
        "porque": "Each stroke has its own place inside the character.",
        "pista": "Start at the top center and move down and to the left.",
    }


def test_trazo_invertido_en_ingles():
    datos = trazo(veredicto("invertido"), EN)

    assert datos["explicacion"]["codigo"] == "TRAZO_INVERTIDO"
    assert datos["explicacion"]["titulo"] == "Stroke 1 is reversed"
    assert datos["explicacion"]["pista"] == "Start at the top center and move down and to the left."


def test_trazo_corto():
    explicacion = trazo(veredicto("incompleto", razon_longitud=0.4))["explicacion"]

    assert explicacion["codigo"] == "TRAZO_CORTO"
    assert explicacion["titulo"] == "Trazo 1: falta el final"
    assert explicacion["porque"] == (
        "Llegaste a cerca del 40 % del trazo. Si no lo terminás, el carácter queda deforme."
    )
    assert explicacion["pista"] == "Mantené el dedo apoyado hasta llegar abajo a la izquierda."


def test_trazo_largo():
    explicacion = trazo(veredicto("incompleto", razon_longitud=2.1))["explicacion"]

    assert explicacion["codigo"] == "TRAZO_LARGO"
    assert explicacion["titulo"] == "Trazo 1: sobra recorrido"
    assert explicacion["porque"] == (
        "Mide cerca del 210 % de lo esperado. Quizá uniste este trazo con el "
        "siguiente; cada uno va por separado."
    )
    assert explicacion["pista"] == "Levantá el dedo cuando llegues abajo a la izquierda."


def test_trazo_corto_y_largo_en_ingles():
    corto = trazo(veredicto("incompleto", razon_longitud=0.4), EN)["explicacion"]
    largo = trazo(veredicto("incompleto", razon_longitud=2.1), EN)["explicacion"]

    assert corto["titulo"] == "Stroke 1: the end is missing"
    assert corto["porque"] == (
        "You reached about 40% of the stroke. If you do not finish it, the "
        "character comes out misshapen."
    )
    assert largo["titulo"] == "Stroke 1: extra length"


def test_trazo_incompleto_sin_razon_longitud_usa_el_respaldo():
    # Un trazos-flask anterior a RF-IA-04 no manda razon_longitud.
    explicacion = trazo(veredicto("incompleto"))["explicacion"]

    assert explicacion["codigo"] == "TRAZO_INCOMPLETO"
    assert explicacion["pista"] == "Empezá arriba al centro y terminá abajo a la izquierda."


def test_trazo_impreciso_dice_donde_se_desvio():
    v = veredicto("impreciso", puntos_lejanos=[{"posicion": 0.9, "desvio": 0.2}, {"posicion": 0.1, "desvio": 0.1}])

    explicacion = trazo(v)["explicacion"]

    assert explicacion["codigo"] == "TRAZO_IMPRECISO"
    assert explicacion["titulo"] == "Trazo 1: desvío al final"
    assert explicacion["pista"] == (
        "Mirá el modelo: el trazo empieza arriba al centro y va hacia abajo y a la izquierda."
    )


def test_trazo_impreciso_sin_puntos_lejanos():
    assert trazo(veredicto("impreciso"))["explicacion"]["titulo"] == "Trazo 1: forma"


def test_trazo_aprobado_no_trae_explicacion():
    datos = trazo({**veredicto("correcto"), "aprobado": True})

    assert datos["acerto"] is True
    assert "explicacion" not in datos
    assert "nota" not in datos


def test_trazo_con_motivo_desconocido_no_trae_explicacion():
    assert "explicacion" not in trazo(veredicto("otro"))


def test_razon_longitud_no_sale_en_la_respuesta():
    # Solo la usa el explicador: los campos de trazo siguen siendo los de v1.
    assert "razon_longitud" not in trazo(veredicto("incompleto", razon_longitud=0.4))


@pytest.mark.parametrize("punto, esperado", [
    ([100, 850], "arriba a la izquierda"), ([500, 800], "arriba al centro"),
    ([900, 700], "arriba a la derecha"), ([500, 400], "en el centro"),
    ([100, 0], "abajo a la izquierda"), ([900, -100], "abajo a la derecha"),
])
def test_zonas_del_lienzo(punto, esperado):
    assert zona(punto) == esperado


@pytest.mark.parametrize("inicio, fin, esperado", [
    ([100, 500], [900, 520], "hacia la derecha"), ([500, 800], [500, 100], "hacia abajo"),
    ([483, 736], [72, 95], "hacia abajo y a la izquierda"), ([200, 200], [800, 800], "hacia arriba y a la derecha"),
    ([900, 500], [100, 480], "hacia la izquierda"),
])
def test_direccion_calculada_con_la_mediana(inicio, fin, esperado):
    assert direccion(inicio, fin) == esperado


@pytest.mark.parametrize("posicion, esperado", [(0.0, "al principio"), (0.5, "en el medio"), (1.0, "al final")])
def test_tramo(posicion, esperado):
    assert tramo(posicion) == esperado


# ----------------------------------------------------- nota de mejora (trazo)


def test_nota_de_mejora_al_final_cuando_el_trazo_gira():
    # 人 trazo 2 dibujado recto hasta el final, sin aplanar: se desvía al final,
    # donde la mediana va hacia la derecha.
    lejanos = [{"posicion": 1.0, "desvio": 0.14}, {"posicion": 0.97, "desvio": 0.13}]
    datos = trazo(aceptable(*lejanos), secuencia=2)

    assert datos["acerto"] is True
    assert datos["puntaje"] == 80 and datos["motivo"] == "correcto"
    assert datos["nota"] == {"codigo": "TRAZO_MEJORA", "texto": "Bien. Al final, el trazo gira hacia la derecha."}
    assert "explicacion" not in datos


def test_nota_de_mejora_en_ingles():
    datos = trazo(aceptable({"posicion": 1.0, "desvio": 0.14}), EN, secuencia=2)

    assert datos["nota"]["texto"] == "Good. At the end, the stroke turns to the right."


@pytest.mark.parametrize("posicion, es, en", [
    (0.1, "Bien. Al principio, seguí más cerca de la guía.", "Good. At the start, stay closer to the guide."),
    (0.5, "Bien. En el medio, seguí más cerca de la guía.", "Good. In the middle, stay closer to the guide."),
    (0.9, "Bien. Al final, seguí más cerca de la guía.", "Good. At the end, stay closer to the guide."),
])
def test_nota_de_mejora_sin_giro_dice_donde_ajustar(posicion, es, en):
    # El trazo 1 de prueba va siempre hacia abajo y a la izquierda: no gira.
    v = aceptable({"posicion": posicion, "desvio": 0.12})

    assert trazo(v)["nota"] == {"codigo": "TRAZO_MEJORA", "texto": es}
    assert trazo(v, EN)["nota"]["texto"] == en


def test_la_nota_usa_el_punto_con_mayor_desvio():
    v = aceptable({"posicion": 0.1, "desvio": 0.10}, {"posicion": 0.5, "desvio": 0.20})

    assert trazo(v)["nota"]["texto"] == "Bien. En el medio, seguí más cerca de la guía."


def test_sin_nota_en_un_correcto_sin_puntos_lejanos():
    datos = trazo({**veredicto("correcto"), "aprobado": True, "puntos_lejanos": []})

    assert datos["acerto"] is True
    assert "nota" not in datos


@pytest.mark.parametrize("motivo", ["impreciso", "invertido", "incompleto", "fuera_de_lugar"])
def test_sin_nota_en_un_trazo_fallado(motivo):
    datos = trazo(veredicto(motivo, puntos_lejanos=[{"posicion": 0.9, "desvio": 0.2}], razon_longitud=0.4))

    assert datos["acerto"] is False
    assert "nota" not in datos
    assert "explicacion" in datos


def test_direccion_local_del_trazo_2_de_人():
    assert direccion_general(MEDIANA_REN_2) == "hacia abajo y a la derecha"
    assert direccion_local(MEDIANA_REN_2, 0.97) == "hacia la derecha"
    assert direccion_local(MEDIANA_REN_2, 0.5) == "hacia abajo y a la derecha"
    assert direccion_local(MEDIANA_REN_2, 0.0) == "hacia abajo y a la derecha"


def test_punto_en_recorre_la_mediana_por_longitud():
    assert punto_en([[0, 0], [10, 0], [10, 10]], 0.5) == (10.0, 0.0)
    assert punto_en([[0, 0], [10, 0], [10, 10]], 1.5) == (10.0, 10.0)
    assert punto_en([[0, 0], [10, 0], [10, 10]], -1) == (0.0, 0.0)


# ----------------------------------------------------------------- pinyin


def test_pinyin_inicial_distinta():
    explicacion = pinyin("好", "gao")["explicacion"]

    assert explicacion == {
        "codigo": "PINYIN_INICIAL",
        "titulo": "Consonante inicial",
        "porque": "La terminación ao está bien. Con otra letra al comienzo, ya es otra palabra.",
        "pista": "Decilo en dos partes, h y ao, y después juntalas con el tercer tono.",
    }


def test_pinyin_inicial_distinta_en_ingles():
    explicacion = pinyin("好", "gao", EN)["explicacion"]

    assert explicacion["codigo"] == "PINYIN_INICIAL"
    assert explicacion["titulo"] == "Initial consonant"
    assert explicacion["pista"] == "Say it in two parts, h and ao, then join them with the third tone."


def test_pinyin_final_distinta():
    explicacion = pinyin("好", "hai")["explicacion"]

    assert explicacion["codigo"] == "PINYIN_FINAL"
    assert explicacion["titulo"] == "Terminación de la sílaba"
    assert explicacion["porque"] == "La consonante h está bien. Con otra terminación, ya es otra palabra."


def test_pinyin_elige_la_lectura_mas_cercana():
    # 长 se lee zhǎng o cháng: "chan" comparte la inicial con cháng.
    explicacion = pinyin("长", "chan")["explicacion"]

    assert explicacion["codigo"] == "PINYIN_FINAL"
    assert explicacion["pista"] == "Decilo en dos partes, ch y ang, y después juntalas con el segundo tono."


def test_pinyin_distinto_con_varias_lecturas():
    explicacion = pinyin("长", "ma")["explicacion"]

    assert explicacion["codigo"] == "PINYIN_DISTINTO"
    assert explicacion["titulo"] == "Inicial y terminación"
    assert explicacion["pista"] == (
        "Decí la lectura principal en voz alta con el tercer tono; según la "
        "palabra, también se lee cháng."
    )


def test_pinyin_distinto_con_una_lectura():
    assert pinyin("人", "ma")["explicacion"]["pista"] == (
        "Mirá el carácter y decí su lectura en voz alta tres veces, con el segundo tono."
    )


@pytest.mark.parametrize("caracter, respuesta", [("好", "gao"), ("好", "hai"), ("长", "ma"), ("人", "ma")])
def test_la_pista_de_pinyin_no_repite_la_lectura_que_muestra_practica(caracter, respuesta):
    # Práctica muestra arriba "La respuesta correcta es: <pinyin>".
    explicacion = pinyin(caracter, respuesta)["explicacion"]

    assert DETALLES[caracter]["pinyin"] not in explicacion["pista"]


@pytest.mark.parametrize("respuesta", ["", "ren ren", "en"])
def test_pinyin_sin_detalle_es_distinto(respuesta):
    # Vacía, de dos sílabas o sin consonante inicial: no se analiza la sílaba.
    assert pinyin("人", respuesta)["explicacion"]["codigo"] == "PINYIN_DISTINTO"


# ------------------------------------------------------------- nota de tono


def test_nota_de_tono_al_acertar():
    datos = pinyin("好", "hao")

    assert datos["acerto"] is True
    assert datos["nota"] == {"codigo": "PINYIN_TONO", "texto": "Se lee hǎo, tercer tono."}
    assert "explicacion" not in datos


def test_nota_de_tono_en_ingles():
    assert pinyin("好", "hao", EN)["nota"]["texto"] == "It is read hǎo, third tone."


def test_nota_usa_la_lectura_que_coincidio():
    assert pinyin("长", "chang")["nota"]["texto"] == "Se lee cháng, segundo tono."
    # Varias lecturas iguales sin tono: gana la que coincide con el tono escrito.
    assert pinyin("了", "liào")["nota"]["texto"] == "Se lee liào, cuarto tono."
    assert pinyin("了", "liao")["nota"]["texto"] == "Se lee liǎo, tercer tono."


def test_nota_tono_neutro():
    assert pinyin("了", "le")["nota"]["texto"] == "Se lee le, tono neutro."
    assert pinyin("了", "le", EN)["nota"]["texto"] == "It is read le, neutral tone."


def test_sin_nota_al_fallar_ni_en_otros_tipos():
    assert "nota" not in pinyin("好", "gao")
    assert "nota" not in significado("好", "good")
    assert "nota" not in trazo({**veredicto("correcto"), "aprobado": True})


@pytest.mark.parametrize("lectura, numero", [("mā", 1), ("má", 2), ("mǎ", 3), ("mà", 4), ("ma", 0), ("lǜ", 4)])
def test_tono_por_la_marca(lectura, numero):
    assert tono(lectura) == numero


@pytest.mark.parametrize("silaba, partes", [("hao", ("h", "ao")), ("zhang", ("zh", "ang")), ("ai", ("", "ai"))])
def test_separar_inicial_y_final(silaba, partes):
    assert separar(silaba) == partes


# ------------------------------------------------------------ significado


def test_significado_parcial():
    explicacion = significado("好", "good house")["explicacion"]

    assert explicacion == {
        "codigo": "SIGNIFICADO_PARCIAL",
        "titulo": "Sobran palabras",
        "porque": "good está bien, pero las otras palabras no son parte del significado.",
        "pista": "Respondé con un solo sentido, por ejemplo: good.",
    }


def test_significado_cercano():
    # "sevn" contra "seven" da 0.89: no llega al umbral de la dificultad 5 (0.92).
    explicacion = significado("七", "sevn", dificultad=5)["explicacion"]

    assert explicacion["codigo"] == "SIGNIFICADO_CERCANO"
    assert explicacion["titulo"] == "Ortografía"
    assert explicacion["pista"] == "Compará letra por letra con la definición: seven."


@pytest.mark.parametrize("respuesta", ["man", "on", "onr"])
def test_parecido_a_un_sentido_corto_no_promete_ortografia(respuesta):
    # Un sentido corto solo acepta coincidencia exacta: pedir que revise la
    # ortografía sería engañoso. Va a DISTINTO, con la definición en la pista.
    explicacion = significado("一", respuesta, dificultad=1)["explicacion"]

    assert explicacion["codigo"] == "SIGNIFICADO_DISTINTO"
    assert "letra por letra" not in explicacion["pista"]


def test_significado_sin_relacion():
    explicacion = significado("好", "mountain")["explicacion"]

    assert explicacion["codigo"] == "SIGNIFICADO_DISTINTO"
    assert explicacion["pista"] == (
        "Definición: good, excellent, fine; proper, suitable; well. "
        "Respondé en inglés, como aparece en el catálogo."
    )


def test_significado_en_espanol_cae_en_distinto_y_recuerda_el_ingles():
    explicacion = significado("好", "bueno", EN)["explicacion"]

    assert explicacion["codigo"] == "SIGNIFICADO_DISTINTO"
    assert explicacion["pista"].endswith("Answer in English, as it appears in the catalog.")


def test_significado_que_acierta_no_trae_explicacion():
    datos = significado("好", "good")

    assert datos["acerto"] is True
    assert "explicacion" not in datos


# ------------------------------------------------------- forma de los textos


CASOS_TODOS_LOS_CODIGOS = [
    lambda c: trazo(veredicto("fuera_de_lugar"), c),
    lambda c: trazo(veredicto("invertido"), c),
    lambda c: trazo(veredicto("incompleto", razon_longitud=0.4), c),
    lambda c: trazo(veredicto("incompleto", razon_longitud=2.1), c),
    lambda c: trazo(veredicto("incompleto"), c),
    lambda c: trazo(veredicto("impreciso", puntos_lejanos=[{"posicion": 0.5, "desvio": 0.2}]), c),
    lambda c: pinyin("好", "gao", c),
    lambda c: pinyin("好", "hai", c),
    lambda c: pinyin("长", "ma", c),
    lambda c: significado("好", "good house", c),
    lambda c: significado("七", "sevn", c, dificultad=5),
    lambda c: significado("好", "mountain", c),
]


@pytest.mark.parametrize("cabeceras", [{}, EN], ids=["es", "en"])
def test_cada_porque_es_una_idea_corta(cabeceras):
    # Una sola idea, en dos frases cortas como mucho y unas 20 palabras.
    codigos = set()
    for caso in CASOS_TODOS_LOS_CODIGOS:
        explicacion = caso(cabeceras)["explicacion"]
        codigos.add(explicacion["codigo"])
        porque = explicacion["porque"]
        assert len(porque.split()) <= 22, porque
        assert len([f for f in porque.split(". ") if f.strip()]) <= 2, porque

    assert len(codigos) == 12


@pytest.mark.parametrize("cabeceras", [{}, EN], ids=["es", "en"])
@pytest.mark.parametrize("posicion, secuencia", [(1.0, 2), (0.1, 1), (0.5, 1)])
def test_la_nota_de_mejora_es_una_frase_corta(cabeceras, posicion, secuencia):
    texto = trazo(aceptable({"posicion": posicion, "desvio": 0.12}), cabeceras, secuencia)["nota"]["texto"]

    assert len(texto.split()) <= 22, texto
    assert len([f for f in texto.split(". ") if f.strip()]) <= 2, texto


# ------------------------------------------------------------ puerto y fábrica


def test_explicar_error_devuelve_none_si_acerto():
    error = ErrorEvaluado(acerto=True, caracter="好", respuesta="gao", datos_correctos=DETALLES["好"])

    assert ExplicadorReglas().explicar_error("pinyin", error) is None


def test_la_fabrica_crea_el_de_reglas():
    explicador = crear_explicador({"EXPLICADOR_ERRORES": "reglas"})

    assert isinstance(explicador, ExplicadorErrores)
    assert explicador.nombre == "reglas"


def test_un_explicador_desconocido_falla_al_arrancar():
    with pytest.raises(ValueError, match="EXPLICADOR_ERRORES='llm' no existe"):
        create_app({"TESTING": True, "EXPLICADOR_ERRORES": "llm"})


class ExplicadorRoto(ExplicadorErrores):
    nombre = "roto"

    def explicar_error(self, tipo, error):
        raise RuntimeError("falla interna")


def test_si_el_explicador_falla_se_responde_sin_explicacion():
    resp = cliente(explicador=ExplicadorRoto()).post(
        URL, json={"tipo": "pinyin", "caracter": "好", "respuesta": "gao"}
    )

    assert resp.status_code == 200
    assert resp.get_json() == {"tipo": "pinyin", "caracter": "好", "acerto": False}
