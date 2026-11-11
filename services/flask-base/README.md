# flask-base

Plantilla de los microservicios Flask de HanZi Mentor. No se despliega: se
copia para crear cada servicio nuevo (`catalogo-flask`, `progreso-flask`,
`evaluacion-flask`, `sesiones-flask`). El estándar completo está en
[`docs/arquitectura/estandar-flask.md`](../../docs/arquitectura/estandar-flask.md).

## Qué trae

| Archivo         | Responsabilidad                                                  |
|-----------------|------------------------------------------------------------------|
| `app.py`        | Fábrica `create_app(config_extra)` y `GET /health`               |
| `config.py`     | Configuración desde variables de entorno                         |
| `db.py`         | SQLAlchemy 2.x: `Base`, sesión por petición, chequeo de conexión |
| `errores.py`    | Errores en JSON (400, 404, 405, 500) y `ErrorDominio`            |
| `i18n.py`       | Flask-Babel: idioma según Accept-Language y `traducir()`         |
| `mensajes.py`   | `N_()`, la marca de textos traducibles para el código sin Flask  |
| `babel.cfg`, `translations/` | Configuración de pybabel y catálogos `es` y `en`    |
| `Dockerfile`    | `python:3.11-slim`, usuario sin privilegios, gunicorn, healthcheck |
| `tests/`        | Pruebas del estándar con pytest                                  |

## Crear un servicio nuevo

```bash
cp -r services/flask-base services/catalogo-flask
cd services/catalogo-flask
rm -rf .venv __pycache__ .pytest_cache db.sqlite3
```

Después:

1. En `Dockerfile` y `.env.example`, cambiar `SERVICE_NAME=flask-base` por el
   nombre del servicio.
2. Crear los modelos en `modelos.py` heredando de `db.Base`, e importarlos en
   `app.py` antes de `iniciar_db(app)` para que se creen sus tablas.
3. Crear las rutas en un blueprint (`rutas.py`) y registrarlo en `create_app`.
   La ruta solo valida la entrada, llama al servicio y arma la respuesta.
4. Poner la lógica de negocio en `servicio.py` y `dominio/`, sin Flask. Las
   reglas incumplidas se lanzan como `ErrorDominio(mensaje, codigo)`.
5. Dentro de una petición, la sesión se obtiene con `obtener_sesion()`; se
   cierra sola al terminar (con rollback si hubo error). Hacer `commit()`
   explícito al escribir.
6. Mantener `tests/test_base.py` y agregar las pruebas propias.
7. Los textos para el usuario se escriben en español y se marcan con
   `N_("...")`; si llevan datos, con marcadores con nombre y `params`:
   `ErrorDominio(N_("Máximo %(n)s"), "CODIGO", params={"n": 50})`. Después
   se actualizan los catálogos (ver "Traducciones").

## Ejecutar

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q

# Desarrollo (SQLite local en db.sqlite3)
.venv/bin/python app.py

# Docker
docker build -t flask-base .
docker run --rm -p 5000:5000 flask-base
curl -s http://localhost:5000/health
# {"estado":"ok","servicio":"flask-base"}
```

## Traducciones

Los mensajes de error salen en español o en inglés según la cabecera
`Accept-Language` (español si no viene o pide otro idioma). Solo cambia el
texto: las claves, el `codigo` y el estado son los mismos.

```bash
.venv/bin/pybabel extract -F babel.cfg --ignore-dirs='.* ._ tests' -o messages.pot .
.venv/bin/pybabel update -i messages.pot -d translations   # init -l <idioma> la primera vez
# completar los msgstr de translations/en/LC_MESSAGES/messages.po
.venv/bin/pybabel compile -d translations
```

Los `.mo` no se suben: los compila el `Dockerfile` y, en las pruebas,
`tests/conftest.py`. Para correr el servicio en local hay que hacer
`pybabel compile` una vez.

## Variables de entorno

| Variable           | Default               | Uso                                          |
|--------------------|-----------------------|----------------------------------------------|
| `SERVICE_NAME`     | `flask-base`          | Nombre que devuelve `/health`                |
| `HOST`             | `0.0.0.0`             | Interfaz de `python app.py`                  |
| `PORT`             | `5000`                | Puerto de `python app.py` y de gunicorn      |
| `FLASK_DEBUG`      | `0`                   | `1` activa debug, solo en local              |
| `DATABASE_URL`     | `sqlite:///db.sqlite3`| URL de SQLAlchemy; vacío = sin base de datos |
| `DB_CREAR_TABLAS`  | `1`                   | Crea las tablas de los modelos al arrancar   |
| `GUNICORN_WORKERS` | `2`                   | Procesos de gunicorn (Docker)                |

En Docker, PostgreSQL se configura con
`DATABASE_URL=postgresql+psycopg2://usuario:clave@db:5432/nombre_db`.

## Respuestas comunes

- `GET /health`: `200 {"estado": "ok", "servicio": "<SERVICE_NAME>"}`. Si hay
  base de datos y no responde: `503 {"estado": "error", "servicio": "...",
  "codigo": "DB_NO_DISPONIBLE"}`.
- Errores: siempre `{"error": "<mensaje>", "codigo": "<CODIGO>"}`, nunca HTML
  ni stack trace.
