"""
Habilita CORS en los dos servicios para que el frontend pueda llamarlos.

El navegador bloquea peticiones entre puertos distintos salvo que el servidor
lo permita explícitamente. curl no aplica esa regla, por eso las pruebas por
terminal funcionaban sin esto.

Uso, parado en la raíz del repo:
    python3 aplicar_cors.py
"""

import pathlib
import sys

SERVICIOS = [
    "services/agente-tutor/config/settings.py",
    "services/contenido/config/settings.py",
]

BLOQUE_CORS = '''
# --- CORS ---
# El frontend corre en otro puerto (5173), así que el navegador lo trata como
# un origen distinto. Sin esto, toda petición desde React sería bloqueada.
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Para probar desde el celular en la misma red, Vite sirve en una IP local
# variable, así que en desarrollo permitimos cualquier origen.
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
'''


def parchear(ruta: pathlib.Path) -> str:
    if not ruta.exists():
        return f"NO EXISTE: {ruta}"

    texto = ruta.read_text(encoding="utf-8")

    if "corsheaders" in texto:
        return f"ya tenía CORS: {ruta}"

    # 1. App
    texto = texto.replace(
        "INSTALLED_APPS = [\n    'rest_framework',",
        "INSTALLED_APPS = [\n    'corsheaders',\n    'rest_framework',",
        1,
    )

    # 2. Middleware — va lo más arriba posible, antes de CommonMiddleware.
    texto = texto.replace(
        "MIDDLEWARE = [\n    'django.middleware.security.SecurityMiddleware',",
        "MIDDLEWARE = [\n    'django.middleware.security.SecurityMiddleware',\n"
        "    'corsheaders.middleware.CorsMiddleware',",
        1,
    )

    # 3. Configuración al final
    texto = texto.rstrip() + "\n" + BLOQUE_CORS

    ruta.write_text(texto, encoding="utf-8")
    return f"listo: {ruta}"


def main():
    raiz = pathlib.Path.cwd()

    if not (raiz / "services").exists():
        print("Corré este script desde la raíz del repo (donde está services/).")
        sys.exit(1)

    for relativa in SERVICIOS:
        print(" ", parchear(raiz / relativa))

    print()
    print("Falta instalar la dependencia en cada servicio:")
    print("  pip install django-cors-headers")


if __name__ == "__main__":
    main()
