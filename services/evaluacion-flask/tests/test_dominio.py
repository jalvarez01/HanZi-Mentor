"""Reglas puras de evaluación. Port de las pruebas EvaluarRespuesta* de
agente-tutor/tutor/tests.py, con los mismos casos."""

import pytest

from dominio.evaluacion import evaluar_respuesta, sentidos


class TestPinyin:
    def test_coincide_con_diacriticos(self):
        assert evaluar_respuesta("pinyin", 3, "xué", {"pinyin": "xué"})

    def test_coincide_sin_diacriticos(self):
        assert evaluar_respuesta("pinyin", 3, "xue", {"pinyin": "xué"})

    def test_no_coincide(self):
        assert not evaluar_respuesta("pinyin", 3, "xiao", {"pinyin": "xué"})

    def test_ignora_mayusculas_y_espacios_de_mas(self):
        assert evaluar_respuesta("pinyin", 3, "  XUÉ ", {"pinyin": "xué"})

    def test_el_tono_no_cuenta(self):
        # Igual que v1: "xuě" y "xué" quedan los dos en "xue".
        assert evaluar_respuesta("pinyin", 3, "xuě", {"pinyin": "xué"})

    def test_ü_tampoco(self):
        # La diéresis también es un diacrítico: "lü" y "lu" coinciden, como en v1.
        assert evaluar_respuesta("pinyin", 3, "lu", {"pinyin": "lǜ"})

    def test_respuesta_vacia_no_coincide(self):
        assert not evaluar_respuesta("pinyin", 3, "", {"pinyin": "xué"})


class TestSignificado:
    def test_coincide_exacto(self):
        assert evaluar_respuesta(
            "significado", 3, "study, learning", {"definicion": "study, learning"}
        )

    def test_coincide_con_orden_de_palabras_distinto(self):
        assert evaluar_respuesta(
            "significado", 3, "learning, study", {"definicion": "study, learning"}
        )

    def test_no_coincide(self):
        assert not evaluar_respuesta(
            "significado", 3, "mountain", {"definicion": "study, learning"}
        )

    def test_pasa_en_dificultad_baja_pero_falla_en_dificultad_alta(self):
        respuesta = "aprendio"  # similar pero no idéntico a la definición
        datos = {"definicion": "aprender"}

        assert evaluar_respuesta("significado", 1, respuesta, datos)
        assert not evaluar_respuesta("significado", 5, respuesta, datos)


class TestSignificadoPorSentidos:
    """Se aparta de v1 a propósito (RF-IA-04): la respuesta se compara también
    con cada sentido de la definición. En v1 "good" para 好 daba 0.17 contra
    la definición completa y fallaba. Los umbrales siguen siendo los de v1
    (test_contrato.py lo comprueba)."""

    HAO = {"definicion": "good, excellent, fine; proper, suitable; well"}
    DA = {"definicion": "big, great, vast, high, deep"}
    REN = {"definicion": "man, person; people"}

    @pytest.mark.parametrize("respuesta, datos", [
        ("good", HAO), ("big", DA), ("person", REN), ("suitable", HAO), ("Well ", HAO),
    ])
    def test_un_sentido_suelto_acierta(self, respuesta, datos):
        assert evaluar_respuesta("significado", 3, respuesta, datos)

    @pytest.mark.parametrize("respuesta, datos", [("mountain", HAO), ("water", DA), ("table", REN)])
    def test_una_palabra_sin_relacion_sigue_fallando(self, respuesta, datos):
        assert not evaluar_respuesta("significado", 3, respuesta, datos)

    def test_la_definicion_completa_sigue_acertando(self):
        assert evaluar_respuesta("significado", 5, self.HAO["definicion"], self.HAO)

    def test_los_umbrales_por_dificultad_se_respetan_por_sentido(self):
        # "persn" contra el sentido "person" da 0.91: pasa hasta la 4 (0.85)
        # y falla en la 5 (0.92).
        assert evaluar_respuesta("significado", 4, "persn", self.REN)
        assert not evaluar_respuesta("significado", 5, "persn", self.REN)

    def test_en_espanol_no_acierta(self):
        # Limitación conocida: las definiciones del catálogo están en inglés.
        assert not evaluar_respuesta("significado", 3, "bueno", self.HAO)

    def test_sentidos_sin_vacios_ni_espacios(self):
        assert sentidos(" good,  excellent ;; fine , ") == ["good", "excellent", "fine"]


class TestSentidosCortos:
    """Un sentido de 1 a 3 letras solo acierta con coincidencia exacta. Con
    similitud, "man" y "on" acertaban para 一 contra "an" y "one" (0.8)."""

    YI = {"definicion": "one; a, an; alone"}
    DA = {"definicion": "big, great, vast, high, deep"}
    HAO = {"definicion": "good, excellent, fine; proper, suitable; well"}
    REN = {"definicion": "man, person; people"}
    QI = {"definicion": "seven"}

    @pytest.mark.parametrize("dificultad", [1, 2, 3, 4, 5])
    @pytest.mark.parametrize("respuesta", ["man", "on"])
    def test_parecido_a_un_sentido_corto_falla_en_toda_dificultad(self, respuesta, dificultad):
        assert not evaluar_respuesta("significado", dificultad, respuesta, self.YI)

    @pytest.mark.parametrize("dificultad", [1, 3, 5])
    @pytest.mark.parametrize("respuesta, datos", [
        ("one", YI), ("an", YI), ("big", DA), (" One. ", YI), ("BIG!", DA),
    ])
    def test_un_sentido_corto_exacto_acierta(self, respuesta, datos, dificultad):
        assert evaluar_respuesta("significado", dificultad, respuesta, datos)

    @pytest.mark.parametrize("respuesta, datos", [
        ("good", HAO), ("person", REN), ("one; a, an; alone", YI), (HAO["definicion"], HAO),
    ])
    def test_sentidos_largos_y_definicion_completa_siguen_acertando(self, respuesta, datos):
        assert evaluar_respuesta("significado", 5, respuesta, datos)

    def test_un_sentido_de_5_letras_sigue_el_umbral(self):
        # "sevn" contra "seven" da 0.89: pasa con 0.85 (dificultad 4), no con 0.92 (5).
        assert evaluar_respuesta("significado", 4, "sevn", self.QI)
        assert not evaluar_respuesta("significado", 5, "sevn", self.QI)

    def test_una_definicion_que_es_un_solo_sentido_corto_exige_exacto(self):
        assert evaluar_respuesta("significado", 1, "big", {"definicion": "big"})
        assert not evaluar_respuesta("significado", 1, "bag", {"definicion": "big"})


class TestCasosInvalidos:
    def test_dificultad_fuera_de_rango_lanza_value_error(self):
        with pytest.raises(ValueError):
            evaluar_respuesta("significado", 6, "algo", {"definicion": "algo"})

    def test_tipo_desconocido_lanza_value_error(self):
        with pytest.raises(ValueError):
            evaluar_respuesta("audio", 3, "algo", {})

    def test_trazo_no_pasa_por_la_regla_pura(self):
        with pytest.raises(ValueError):
            evaluar_respuesta("trazo", 3, {}, {})


class TestVariasLecturas:
    """El catálogo manda `lecturas` con todas las pronunciaciones (pinyin primero)."""

    CHANG = {"pinyin": "zhǎng", "lecturas": ["zhǎng", "cháng"]}
    DE = {"pinyin": "dé", "lecturas": ["dé", "de", "děi"]}
    LE = {"pinyin": "le", "lecturas": ["le", "liǎo", "liào"]}
    REN = {"pinyin": "rén", "lecturas": ["rén"]}

    @pytest.mark.parametrize("respuesta", ["cháng", "chang", "zhǎng", "ZHANG"])
    def test_长_acepta_cualquier_lectura(self, respuesta):
        assert evaluar_respuesta("pinyin", 3, respuesta, self.CHANG)

    @pytest.mark.parametrize("respuesta", ["dé", "de", "děi", "dei"])
    def test_得_acepta_cualquier_lectura(self, respuesta):
        assert evaluar_respuesta("pinyin", 3, respuesta, self.DE)

    @pytest.mark.parametrize("respuesta", ["le", "liǎo", "liao"])
    def test_了_acepta_cualquier_lectura(self, respuesta):
        assert evaluar_respuesta("pinyin", 3, respuesta, self.LE)

    @pytest.mark.parametrize("datos", [CHANG, DE, LE, REN])
    def test_una_respuesta_incorrecta_sigue_fallando(self, datos):
        assert not evaluar_respuesta("pinyin", 3, "ma", datos)

    def test_un_caracter_de_una_sola_lectura(self):
        assert evaluar_respuesta("pinyin", 3, "ren", self.REN)
        assert not evaluar_respuesta("pinyin", 3, "chang", self.REN)

    def test_catalogo_anterior_sin_lecturas_usa_el_pinyin(self):
        assert evaluar_respuesta("pinyin", 3, "zhang", {"pinyin": "zhǎng"})
        assert not evaluar_respuesta("pinyin", 3, "chang", {"pinyin": "zhǎng"})

    @pytest.mark.parametrize("lecturas", [None, [], "cháng", [None, ""]])
    def test_lecturas_vacias_o_raras_vuelven_al_pinyin(self, lecturas):
        datos = {"pinyin": "zhǎng", "lecturas": lecturas}

        assert evaluar_respuesta("pinyin", 3, "zhang", datos)
        assert not evaluar_respuesta("pinyin", 3, "chang", datos)
