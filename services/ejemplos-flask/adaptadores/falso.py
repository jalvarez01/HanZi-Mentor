"""Adaptador falso: datos fijos, sin red.

Sirve para las pruebas y para levantar el servicio sin depender de la API
externa (por ejemplo, en una demo sin internet).
"""

from dominio.ejemplo import Ejemplo
from dominio.puertos import ProveedorEjemplos

_EJEMPLOS = {
    "学": [
        ("我学中文。", "wǒ xué zhōngwén", {"es": "Estudio chino.", "en": "I study Chinese."}),
        ("他是学生。", "tā shì xuésheng", {"es": "Él es estudiante.", "en": "He is a student."}),
        ("我们去学校。", "wǒmen qù xuéxiào", {"es": "Vamos a la escuela.", "en": "We go to school."}),
    ],
    "人": [
        ("他是好人。", "tā shì hǎo rén", {"es": "Él es una buena persona.", "en": "He is a good person."}),
        ("这里人很多。", "zhèlǐ rén hěn duō", {"es": "Aquí hay mucha gente.", "en": "There are many people here."}),
    ],
}


class EjemplosFalsos(ProveedorEjemplos):
    nombre = "falso"

    def obtener(self, hanzi, idioma, limite):
        return [
            Ejemplo(texto=texto, pinyin=pinyin, traduccion=traducciones.get(idioma))
            for texto, pinyin, traducciones in _EJEMPLOS.get(hanzi, [])
        ][:limite]
