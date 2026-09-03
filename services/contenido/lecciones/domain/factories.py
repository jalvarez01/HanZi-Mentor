class EjercicioFactory:
    """
    Factory: encapsula la creación de las distintas variantes de Ejercicio.
    Si mañana aparece un tipo nuevo (pinyin, opción múltiple), solo se
    extiende esta clase, sin tocar el Builder ni el Service.
    """
 
    @staticmethod
    def crear(tipo, leccion, caracter):
        from lecciones.models import Ejercicio, TIPOS_EJERCICIO
 
        tipos_validos = dict(TIPOS_EJERCICIO)
        if tipo not in tipos_validos:
            raise ValueError(f"Tipo de ejercicio inválido: {tipo}")
 
        return Ejercicio(leccion=leccion, caracter=caracter, tipo=tipo)