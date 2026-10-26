"""Reglas puras de evaluación. Port de las pruebas EvaluarRespuesta* de
agente-tutor/tutor/tests.py, con los mismos casos."""

import pytest

from dominio.evaluacion import evaluar_respuesta


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
