# progreso-flask

Microservicio Flask del progreso del usuario y el repaso espaciado (tarea
T11 del Strangler Pattern). Reemplaza en `/api/v2/` a la app `progreso` del
servicio Django `services/agente-tutor` y a la parte de
`ResponderEjercicioService` que actualiza el progreso. Tiene su propia base
de datos y ninguna dependencia de Django. v1 (`/api/v1/tutor/progreso/`)
sigue funcionando mientras conviven las dos versiones (T17).

Sigue el estándar de [`docs/arquitectura/estandar-flask.md`](../../docs/arquitectura/estandar-flask.md)
y parte de la plantilla `services/flask-base`.

## Estructura

| Archivo              | Responsabilidad                                                   |
|----------------------|-------------------------------------------------------------------|
| `app.py`             | Fábrica `create_app()`: config, base, errores, rutas, `/health`   |
| `config.py`          | Configuración desde variables de entorno                          |
| `db.py`              | SQLAlchemy 2.x: `Base`, sesión por petición, chequeo de conexión  |
| `modelos.py`         | `ProgresoUsuario` y el tipo `FechaUTC`                            |
| `dominio/progreso.py`| Reglas de acierto, error, agenda de repaso y desbloqueo de nivel  |
| `dominio/repaso.py`  | Repaso espaciado (SM-2 simplificado) y tasa de acierto            |
| `repositorio.py`     | Acceso a datos y el resumen que devuelve la API                   |
| `servicio.py`        | Casos de uso: consultar, registrar respuesta, refuerzos           |
| `validacion.py`      | UUID, cuerpo de la respuesta y `limite` (400 `ENTRADA_INVALIDA`)  |
| `serializacion.py`   | Fechas en ISO 8601 con `Z`, igual que DRF                         |
| `rutas.py`           | Blueprint con los tres endpoints                                  |
| `errores.py`         | Manejadores globales; todo error responde JSON                    |
| `crear_base.py`      | Crea la base PostgreSQL de `DATABASE_URL` si no existe (idempotente) |
| `docker-entrypoint.sh` | En Docker, crea la base y las tablas antes de arrancar gunicorn |

Equivalencias con v1:

| Django (`services/agente-tutor`)  | Flask (`services/progreso-flask`)        |
|-----------------------------------|------------------------------------------|
| `progreso/models.py`              | `modelos.py`                             |
| `progreso/repositories.py`        | `repositorio.py`                         |
| `progreso/services.py`, `views.py`| `servicio.py`, `rutas.py`                |
| `tutor/domain/progreso_logic.py`  | `dominio/progreso.py`                    |
| `tutor/domain/repaso.py`          | `dominio/repaso.py` (sin `django.utils.timezone`) |
| progreso en `ResponderEjercicioService` | `servicio.registrar_respuesta`     |

`ProgresoUsuario` conserva `registrar_error()` y `registrar_acierto()`
como atajos a las reglas del dominio. Ninguno guarda: el commit lo hace el
servicio.

## Ejecutar

```bash
cd services/progreso-flask
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q

# En macOS el puerto 5000 lo usa AirPlay: conviene otro en local.
PORT=5083 .venv/bin/python app.py
# o, como en producción:
.venv/bin/gunicorn -w 2 -b 127.0.0.1:5083 "app:create_app()"
```

Sin `DATABASE_URL` usa SQLite en `db.sqlite3`. No hace falta cargar datos:
el progreso de un usuario se crea con su primera respuesta.

## Variables de entorno

| Variable           | Default                | Uso                                          |
|--------------------|------------------------|----------------------------------------------|
| `SERVICE_NAME`     | `progreso-flask`       | Nombre que devuelve `/health`                |
| `HOST`             | `0.0.0.0`              | Interfaz de `python app.py`                  |
| `PORT`             | `5000`                 | Puerto de `python app.py` y de gunicorn      |
| `FLASK_DEBUG`      | `0`                    | `1` activa debug, solo en local              |
| `DATABASE_URL`     | `sqlite:///db.sqlite3` | URL de SQLAlchemy de la base propia          |
| `DB_CREAR_TABLAS`  | `1`                    | Crea las tablas al arrancar                  |
| `GUNICORN_WORKERS` | `2`                    | Procesos de gunicorn (Docker)                |

Ver `.env.example`.

## Base de datos en Docker

Sigue el esquema del equipo, el mismo de `catalogo-flask`: un solo
PostgreSQL (`db` en `docker-compose.yml`) con una base por servicio. La de
este servicio es `db_progreso`:

`DATABASE_URL=postgresql+psycopg2://hanzimentor:hanzimentor@db:5432/db_progreso`

Arranque en Docker, en orden:

1. `crear_base.py` crea `db_progreso` si no existe. Si ya existe, solo lo
   informa, así que reiniciar el contenedor no falla.
2. Se crean las tablas una sola vez, antes de que arranquen los workers.
3. gunicorn.

Ningún paso detiene el arranque: si PostgreSQL no responde queda un `AVISO`
en el log y `/health` responde 503 hasta que la base vuelva.

Los clientes (agente-tutor, flask_sesiones) usan la URL base del servicio,
sin `/api/v2`, con la misma convención que `CATALOGO_URL`:
`PROGRESO_URL=http://flask_progreso:5000`.

## Idioma de los mensajes

Los textos para el usuario (`error`, `detalle`, `aviso`) salen en español o
en inglés según la cabecera `Accept-Language`; sin cabecera, o con otro
idioma, en español. Las claves, el `codigo` y el estado no cambian. Usa
Flask-Babel como `services/flask-base` (`i18n.py`, `mensajes.py`,
`babel.cfg` y `translations/`). Para agregar o cambiar un texto, ver
"Traducciones" en el README de flask-base. El `Dockerfile` compila los
`.mo`; para correrlo en local, `.venv/bin/pybabel compile -d translations`.

```bash
curl -s http://localhost:5000/no/existe -H "Accept-Language: en"
# {"error":"Resource not found","codigo":"NO_ENCONTRADO"}
```

## Contrato

### `GET /api/v2/progreso/<usuario_id>/`

Misma respuesta que `GET /api/progreso/<usuario_id>/` de agente-tutor:
mismas claves, mismo orden y mismos valores (`tests/test_contrato.py` lo
compara con `ProgresoUsuarioSerializer`). Un usuario sin progreso recibe
los valores iniciales y no se guarda nada.

```bash
curl -s http://localhost:5083/api/v2/progreso/3fa85f64-5717-4562-b3fc-2c963f66afa6/
```

```json
{"usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "nivel_hsk": 1, "nivel_max_desbloqueado": 1,
 "tasa_acierto": 0.5, "caracteres_dominados": [], "errores_frecuentes": {}, "aciertos_consecutivos": {},
 "proximo_repaso": null, "actualizado_en": null, "total_dominados": 0, "total_por_reforzar": 0,
 "caracteres_debiles": []}
```

### `POST /api/v2/progreso/<usuario_id>/respuestas/`

Uso interno: lo llamará `flask_sesiones` (T12) en vez de tocar estas tablas.
Cuerpo: `{"caracter": "学", "acerto": true}` (`caracter` de 1 a 8
caracteres, `acerto` booleano). Aplica las mismas reglas que v1:

- Acierto: descuenta un fallo, suma a la racha y, si no quedan fallos, el
  carácter pasa a `caracteres_dominados`.
- Error: suma un fallo, corta la racha y lo saca de dominados.
- La tasa de acierto es una media móvil (peso 0.1).
- El próximo repaso se agenda en 1, 3, 7, 16, 35 o 90 días según la racha,
  o en 12 horas si se falló. `proximo_repaso` es el más cercano de la agenda.

Responde `200` con el progreso actualizado, en la misma forma que el GET:

```bash
curl -s -X POST http://localhost:5083/api/v2/progreso/3fa85f64-5717-4562-b3fc-2c963f66afa6/respuestas/ \
  -H "Content-Type: application/json" -d '{"caracter": "学", "acerto": false}'
```

```json
{"usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "nivel_hsk": 1, "nivel_max_desbloqueado": 1,
 "tasa_acierto": 0.495, "caracteres_dominados": [], "errores_frecuentes": {"学": 1},
 "aciertos_consecutivos": {"学": 0}, "proximo_repaso": "2026-10-24T07:53:19.889049Z",
 "actualizado_en": "2026-10-23T19:53:19.889585Z", "total_dominados": 0, "total_por_reforzar": 1,
 "caracteres_debiles": [{"caracter": "学", "fallos": 1}]}
```

### `GET /api/v2/progreso/<usuario_id>/refuerzos/?limite=3`

Los caracteres con más fallos, de peor a mejor (la lógica de
`caracteres_a_reforzar` de v1). `limite` entre 1 y 50, por defecto 3.

```json
{"usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "caracteres": ["人"]}
```

### `GET /health`

```bash
curl -s http://localhost:5083/health
# {"estado":"ok","servicio":"progreso-flask"}
# Si la base no responde: 503 {"estado":"error","servicio":"progreso-flask","codigo":"DB_NO_DISPONIBLE"}
```

### Errores

Siempre `{"error": "<mensaje>", "codigo": "<CODIGO>"}`:

| Estado | `codigo`              | Cuándo                                              |
|--------|-----------------------|-----------------------------------------------------|
| 400    | `ENTRADA_INVALIDA`    | UUID inválido, cuerpo inválido o `limite` fuera de rango |
| 404    | `NO_ENCONTRADO`       | Ruta inexistente                                    |
| 405    | `METODO_NO_PERMITIDO` | Método HTTP no soportado                            |
| 500    | `ERROR_INTERNO`       | Error inesperado (sin stack trace)                  |

Diferencia con v1: un `usuario_id` que no es UUID respondía 404 (la ruta no
coincidía); acá responde 400 con `ENTRADA_INVALIDA`. También se acepta en
mayúsculas y se devuelve normalizado.

## Docker

```bash
docker build -t progreso-flask services/progreso-flask
docker run --rm -p 5083:5000 progreso-flask   # SQLite dentro del contenedor

# Con PostgreSQL, como en docker-compose.yml:
docker run --rm -p 5083:5000 \
  -e DATABASE_URL=postgresql+psycopg2://hanzimentor:hanzimentor@db:5432/db_progreso \
  --network <red de compose> progreso-flask
```
