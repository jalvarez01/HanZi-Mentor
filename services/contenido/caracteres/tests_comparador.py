"""Pruebas del comparador de trazos (RF-APR-01).

No requieren base de datos ni Django: el comparador es una función pura
sobre listas de puntos.
"""

import random
from django.test import SimpleTestCase

from caracteres.domain.comparador import (
    DESPLAZAMIENTO_Y,
    LIENZO,
    comparar_trazo,
    longitud_total,
    normalizar_puntos,
    remuestrear,
    suavizar,
)

# Trazo diagonal, equivalente al primero del carácter 人.
MEDIANA = [[458, 800], [435, 764], [400, 700], [350, 620], [300, 540]]

ANCHO = ALTO = 300


def a_canvas(punto, ruido=0.0):
    """Convierte un punto del sistema 1024 a píxeles del canvas."""
    x, y = punto
    return [
        x / LIENZO * ANCHO + random.uniform(-ruido, ruido),
        (DESPLAZAMIENTO_Y - y) / LIENZO * ALTO + random.uniform(-ruido, ruido),
    ]


def densificar(puntos, por_segmento=40):
    """Interpola para simular la captura densa de un dedo sobre la pantalla."""
    resultado = []
    for i in range(len(puntos) - 1):
        for t in range(por_segmento):
            f = t / por_segmento
            resultado.append([
                puntos[i][0] + (puntos[i + 1][0] - puntos[i][0]) * f,
                puntos[i][1] + (puntos[i + 1][1] - puntos[i][1]) * f,
            ])
    resultado.append(puntos[-1])
    return resultado


def trazo_usuario(mediana=MEDIANA, ruido=0.0, semilla=7, invertir=False):
    random.seed(semilla)
    base = list(reversed(mediana)) if invertir else mediana
    return [a_canvas(p, ruido) for p in densificar(base)]


class NormalizacionTest(SimpleTestCase):
    def test_invierte_el_eje_vertical(self):
        """El canvas crece hacia abajo; el dataset, hacia arriba."""
        arriba = normalizar_puntos([[150, 0]], ANCHO, ALTO)[0]
        abajo = normalizar_puntos([[150, ALTO]], ANCHO, ALTO)[0]

        self.assertGreater(arriba[1], abajo[1])

    def test_el_centro_del_canvas_cae_en_el_centro_horizontal(self):
        centro = normalizar_puntos([[ANCHO / 2, ALTO / 2]], ANCHO, ALTO)[0]
        self.assertAlmostEqual(centro[0], LIENZO / 2, places=1)

    def test_lienzo_invalido_no_revienta(self):
        self.assertEqual(normalizar_puntos([[1, 1]], 0, 0), [])


class RemuestreoTest(SimpleTestCase):
    def test_devuelve_la_cantidad_pedida(self):
        muestra = remuestrear([[0, 0], [10, 0], [20, 0]], cantidad=16)
        self.assertEqual(len(muestra), 16)

    def test_conserva_los_extremos(self):
        muestra = remuestrear([[0, 0], [10, 0], [20, 0]], cantidad=8)
        self.assertEqual(muestra[0], (0, 0))
        self.assertEqual(muestra[-1], (20, 0))

    def test_reparte_los_puntos_de_forma_uniforme(self):
        """Sobre una recta, los puntos deben quedar equiespaciados."""
        muestra = remuestrear([[0, 0], [100, 0]], cantidad=5)
        xs = [p[0] for p in muestra]

        for esperado, obtenido in zip([0, 25, 50, 75, 100], xs):
            self.assertAlmostEqual(obtenido, esperado, places=6)

    def test_curva_degenerada(self):
        """Un solo punto repetido no debe romper el remuestreo."""
        muestra = remuestrear([[5, 5], [5, 5]], cantidad=4)
        self.assertEqual(len(muestra), 4)


class SuavizadoTest(SimpleTestCase):
    def test_reduce_la_longitud_de_una_curva_con_ruido(self):
        """El temblor infla el recorrido; suavizar debe devolverlo a lo real."""
        random.seed(1)
        recta = [[i, 0] for i in range(100)]
        con_ruido = [[x, y + random.uniform(-3, 3)] for x, y in recta]

        self.assertGreater(longitud_total(con_ruido), longitud_total(recta) * 1.5)
        self.assertLess(longitud_total(suavizar(con_ruido)), longitud_total(con_ruido))

    def test_no_altera_curvas_muy_cortas(self):
        puntos = [[0, 0], [1, 1]]
        self.assertEqual(suavizar(puntos), puntos)


class ComparacionTest(SimpleTestCase):
    def test_trazo_perfecto_obtiene_puntaje_alto(self):
        resultado = comparar_trazo(trazo_usuario(), MEDIANA, ANCHO, ALTO)

        self.assertTrue(resultado.aprobado)
        self.assertEqual(resultado.motivo, "correcto")
        self.assertGreaterEqual(resultado.puntaje, 95)

    def test_el_temblor_de_la_mano_sigue_aprobando(self):
        """Nadie dibuja con el dedo sin temblar; eso no puede reprobar."""
        resultado = comparar_trazo(trazo_usuario(ruido=8), MEDIANA, ANCHO, ALTO)

        self.assertTrue(resultado.aprobado)
        self.assertGreaterEqual(resultado.puntaje, 80)

    def test_detecta_el_trazo_hecho_al_reves(self):
        resultado = comparar_trazo(
            trazo_usuario(invertir=True), MEDIANA, ANCHO, ALTO
        )

        self.assertFalse(resultado.aprobado)
        self.assertTrue(resultado.invertido)
        self.assertEqual(resultado.motivo, "invertido")

    def test_detecta_el_trazo_incompleto(self):
        completo = trazo_usuario()
        resultado = comparar_trazo(
            completo[: len(completo) // 3], MEDIANA, ANCHO, ALTO
        )

        self.assertFalse(resultado.aprobado)
        self.assertEqual(resultado.motivo, "incompleto")
        self.assertLess(resultado.razon_longitud, 0.6)

    def test_rechaza_un_trazo_con_forma_distinta(self):
        horizontal = [[20 + i * 6, 150] for i in range(45)]
        resultado = comparar_trazo(horizontal, MEDIANA, ANCHO, ALTO)

        self.assertFalse(resultado.aprobado)
        self.assertEqual(resultado.puntaje, 0)

    def test_rechaza_un_trazo_paralelo_pero_desplazado(self):
        """Misma forma en el lugar equivocado no es el mismo trazo."""
        corrido = [[p[0] + 25, p[1] + 25] for p in trazo_usuario()]
        resultado = comparar_trazo(corrido, MEDIANA, ANCHO, ALTO)

        self.assertFalse(resultado.aprobado)
        self.assertEqual(resultado.motivo, "impreciso")

    def test_sin_trazo_del_usuario(self):
        resultado = comparar_trazo([], MEDIANA, ANCHO, ALTO)

        self.assertFalse(resultado.aprobado)
        self.assertEqual(resultado.motivo, "vacio")
        self.assertEqual(resultado.puntaje, 0)

    def test_sin_mediana_de_referencia(self):
        resultado = comparar_trazo(trazo_usuario(), [], ANCHO, ALTO)

        self.assertFalse(resultado.aprobado)
        self.assertEqual(resultado.motivo, "vacio")

    def test_funciona_con_canvas_de_otro_tamano(self):
        """El veredicto no debe depender del tamaño de pantalla."""
        random.seed(7)
        grande = [
            [p[0] / LIENZO * 900, (DESPLAZAMIENTO_Y - p[1]) / LIENZO * 900]
            for p in densificar(MEDIANA)
        ]
        resultado = comparar_trazo(grande, MEDIANA, 900, 900)

        self.assertTrue(resultado.aprobado)
        self.assertGreaterEqual(resultado.puntaje, 95)

    def test_informa_donde_se_desvio(self):
        corrido = [[p[0] + 25, p[1] + 25] for p in trazo_usuario()]
        resultado = comparar_trazo(corrido, MEDIANA, ANCHO, ALTO)

        self.assertTrue(resultado.puntos_lejanos)
        for punto in resultado.puntos_lejanos:
            self.assertGreaterEqual(punto["posicion"], 0.0)
            self.assertLessEqual(punto["posicion"], 1.0)

    def test_el_resultado_se_serializa(self):
        resultado = comparar_trazo(trazo_usuario(), MEDIANA, ANCHO, ALTO)
        datos = resultado.a_dict()

        self.assertIn("aprobado", datos)
        self.assertIn("puntaje", datos)
        self.assertIn("detalle", datos)
