# catalogo-flask

Microservicio Flask del catálogo: caracteres, trazos y lecciones (tarea T13
del Strangler Pattern). Reemplaza en `/api/v2/` a las apps `caracteres` y
`lecciones` del servicio Django `services/contenido`, con su propia base de
datos y sin ninguna dependencia de Django. La versión v1 sigue funcionando
como respaldo mientras conviven las dos (T17).

Sigue el estándar de [`docs/arquitectura/estandar-flask.md`](../../docs/arquitectura/estandar-flask.md)
y parte de la plantilla `services/flask-base`.

También expone `GET /api/v2/publico/resumen/` (T14), el servicio que consume
el equipo aliado: un resumen del catálogo con CORS abierto (ver abajo).

La validación de trazos **no** está acá: vive en `services/trazos-flask`
(`POST /api/v2/trazos/validar/`). Este servicio entrega la mediana de cada
trazo en el detalle del carácter, que es lo que trazos-flask necesita.

## Estructura

| Archivo               | Responsabilidad                                                  |
|-----------------------|------------------------------------------------------------------|
| `app.py`              | Fábrica `create_app()`: config, base, errores, rutas, `/health`  |
| `config.py`           | Configuración desde variables de entorno                         |
| `db.py`               | SQLAlchemy 2.x: `Base`, sesión por petición, chequeo de conexión |
| `modelos.py`          | `Caracter`, `Trazo`, `Leccion`, `Ejercicio`                      |
| `hsk.py`              | Listas de caracteres por nivel HSK (copia de contenido)          |
| `dominio/lecciones.py`| Builder y Factory de ejercicios, sin Flask ni SQLAlchemy         |
| `servicio.py`         | Casos de uso: consultan la base y delegan en el dominio          |
| `validacion.py`       | Valida query string y cuerpo JSON (400 `ENTRADA_INVALIDA`)       |
| `serializacion.py`    | Arma el JSON con los mismos campos que los serializers de v1     |
| `rutas.py`            | Blueprint con los cuatro endpoints                               |
| `errores.py`          | Manejadores globales; todo error responde JSON                   |
| `carga.py`, `cargar.py` | Importación de Make Me a Hanzi (lógica y línea de comandos)    |
| `docker-entrypoint.sh`| En Docker, crea la base y carga el dataset si la base está vacía |
| `crear_base.py`       | Crea la base PostgreSQL de `DATABASE_URL` si no existe (idempotente) |
| `descargar_datos.py`  | Descarga Make Me a Hanzi de GitHub si no hay volumen y la base está vacía |

Equivalencias con v1:

| Django (`services/contenido`)                 | Flask (`services/catalogo-flask`)          |
|-----------------------------------------------|--------------------------------------------|
| `caracteres/models.py`, `lecciones/models.py` | `modelos.py`                               |
| `Meta.ordering`                               | `ORDEN_CARACTERES`, `order_by` en relaciones |
| `*/serializers.py`                            | `validacion.py` y `serializacion.py`       |
| `lecciones/domain/builders.py`, `factories.py`| `dominio/lecciones.py`                     |
| `lecciones/services.py`, vistas               | `servicio.py`, `rutas.py`                  |
| `manage.py cargar_hanzi`                      | `python cargar.py`                         |

## Ejecutar

```bash
cd services/catalogo-flask
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q

# Cargar caracteres (ver "Dataset" abajo) y levantar el servicio.
# En macOS el puerto 5000 lo usa AirPlay: conviene otro en local.
.venv/bin/python cargar.py --ruta ../contenido/data_hanzi --nivel 1 2
PORT=5081 .venv/bin/python app.py
# o, como en producción:
.venv/bin/gunicorn -w 2 -b 127.0.0.1:5081 "app:create_app()"
```

Sin `DATABASE_URL` el servicio usa SQLite en `db.sqlite3`, dentro de la
carpeta desde donde se ejecuta. `cargar.py` y la app leen la misma variable,
así que comparten la base.

## Dataset de Make Me a Hanzi

Los caracteres vienen de [Make Me a Hanzi](https://github.com/skishore/makemeahanzi)
(licencias Arphic y Unihan, ver `COPYING` en ese repositorio). Hacen falta
dos archivos, ambos con un objeto JSON por línea:

- `dictionary.txt`: pinyin, definición, radical y descomposición.
- `graphics.txt`: el path SVG y la mediana de cada trazo.

El dataset pesa varios MB y no está en el repo. Se usa la misma carpeta que
`contenido`, que ya está en `.gitignore`:

```bash
# Desde la raíz del repo
git clone --depth 1 https://github.com/skishore/makemeahanzi services/contenido/data_hanzi
ls services/contenido/data_hanzi/dictionary.txt services/contenido/data_hanzi/graphics.txt
```

Opciones de `cargar.py`:

| Opción            | Uso                                                                 |
|-------------------|---------------------------------------------------------------------|
| `--ruta RUTA`     | Carpeta con `dictionary.txt` y `graphics.txt` (obligatoria)         |
| `--nivel 1 2 ...` | Niveles HSK a importar, según `hsk.py`. Por defecto 1 y 2            |
| `--todos`         | Importa todo el archivo; los que no son HSK quedan con `nivel_hsk` nulo |
| `--limpiar`       | Borra caracteres, trazos y ejercicios antes de importar             |
| `--si-vacia`      | Solo importa si la base no tiene caracteres                         |

Volver a correrlo actualiza los caracteres existentes y reemplaza sus
trazos, sin duplicar. Para pruebas hay un dataset mínimo en
`tests/datos/makemeahanzi` (人, 大, 两 y 丶).

## Variables de entorno

| Variable           | Default                | Uso                                          |
|--------------------|------------------------|----------------------------------------------|
| `SERVICE_NAME`     | `catalogo-flask`       | Nombre que devuelve `/health`                |
| `HOST`             | `0.0.0.0`              | Interfaz de `python app.py`                  |
| `PORT`             | `5000`                 | Puerto de `python app.py` y de gunicorn      |
| `FLASK_DEBUG`      | `0`                    | `1` activa debug, solo en local              |
| `DATABASE_URL`     | `sqlite:///db.sqlite3` | URL de SQLAlchemy de la base propia          |
| `DB_CREAR_TABLAS`  | `1`                    | Crea las tablas al arrancar                  |
| `GUNICORN_WORKERS` | `2`                    | Procesos de gunicorn (Docker)                |

Ver `.env.example`. En Docker (`docker-compose.yml`) la base es `db_catalogo`
dentro del PostgreSQL compartido `db`:
`DATABASE_URL=postgresql+psycopg2://hanzimentor:hanzimentor@db:5432/db_catalogo`.

Arranque en Docker, en orden:

1. `crear_base.py` crea `db_catalogo` si no existe.
2. Si no hay dataset montado en `/datos` y la base está vacía,
   `descargar_datos.py` baja `dictionary.txt` y `graphics.txt` (unos 33 MB)
   a `/tmp/makemeahanzi`.
3. `cargar.py --si-vacia` importa HSK 1 a 6 solo si la base está vacía.

Ningún paso detiene el arranque: si falla, queda un `AVISO` en el log y el
servicio arranca con el catálogo vacío.

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

Las respuestas exitosas tienen **exactamente** las mismas claves, en el
mismo orden, que v1 (`/api/v1/...` en el gateway). `tests/test_contrato.py`
lo comprueba leyendo los serializers de `services/contenido`.

### `GET /api/v2/caracteres/?nivel=&excluir=&limite=`

- `nivel`: entero, opcional. Sin él lista todos los niveles.
- `excluir`: hanzi separados por coma, opcional.
- `limite`: entero entre 1 y 100, por defecto 20.

Orden: `nivel_hsk`, `frecuencia`, `hanzi`, con los no clasificados al final.

```bash
curl -s "http://localhost:5081/api/v2/caracteres/?nivel=1&excluir=人&limite=4"
```

```json
{"caracteres": [{"hanzi": "大", "pinyin": "dà", "definicion": "big, great, vast, large, high", "nivel_hsk": 1}]}
```

### `GET /api/v2/caracteres/<hanzi>/`

Incluye los trazos en orden de escritura, con su path SVG y su mediana.

```bash
curl -s http://localhost:5081/api/v2/caracteres/人/
```

```json
{"hanzi": "人", "pinyin": "rén", "definicion": "man; people; mankind; someone else",
 "radical": "人", "descomposicion": "？", "nivel_hsk": 1,
 "trazos": [
   {"secuencia": 1, "path_svg": "M 458 800 Q 400 700 300 540 Z",
    "mediana": [[458, 800], [435, 764], [400, 700], [350, 620], [300, 540]]},
   {"secuencia": 2, "path_svg": "M 520 560 Q 600 400 760 200 Z",
    "mediana": [[520, 560], [600, 400], [760, 200]]}]}
```

### `POST /api/v2/lecciones/generar/`

Cuerpo: `usuario_id` (UUID, o un entero como acepta DRF), `nivel_hsk` (1 a
6) y `cantidad` (1 a 50, por defecto 10). Responde `201`.

```bash
curl -s -X POST http://localhost:5081/api/v2/lecciones/generar/ \
  -H "Content-Type: application/json" \
  -d '{"usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "nivel_hsk": 1, "cantidad": 2}'
```

```json
{"id": 1, "usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "nivel_hsk": 1,
 "creada_en": "2026-10-23T12:12:56.829128Z",
 "ejercicios": [
   {"id": 1, "tipo": "trazo", "caracter": {"hanzi": "大", "pinyin": "dà", "definicion": "big, great, vast, large, high", "nivel_hsk": 1}, "completado": false},
   {"id": 2, "tipo": "trazo", "caracter": {"hanzi": "人", "pinyin": "rén", "definicion": "man; people; mankind; someone else", "nivel_hsk": 1}, "completado": false}]}
```

Los caracteres salen del nivel exacto; si no alcanzan, se completa con los
no clasificados. El tipo de cada ejercicio es aleatorio.

### `GET /api/v2/lecciones/<id>/`

Misma forma que la respuesta de `generar`.

### `GET /api/v2/publico/resumen/?lang=&nivel=`

Servicio para el equipo aliado (T14): totales del catálogo y un carácter del
día. Va en un blueprint aparte (`rutas_publico.py`) y responde con
`Access-Control-Allow-Origin: *`, también en sus errores (incluidos 404 y 405
bajo `/api/v2/publico/`), para que el aliado pueda consumirlo desde un
navegador. Es de solo lectura y no usa credenciales.

- `lang`: `es` o `en`, opcional. Elige el idioma de los errores, aunque la
  petición no traiga `Accept-Language` (lo normal si el aliado llama desde su
  backend); si vienen los dos, manda `lang`. Sin `lang` se usa
  `Accept-Language`, como en el resto del servicio. No cambia la respuesta
  exitosa: no tiene textos para traducir.
- `nivel`: entero de 1 a 6, opcional. Elige el carácter del día entre los de
  ese nivel; los totales siempre son de todo el catálogo.
- `caracter_del_dia`: el mismo durante todo el día (UTC). Sale de la fecha,
  no del azar, así que dos peticiones del mismo día devuelven el mismo.
  `null` si no hay caracteres cargados en ese nivel.
- `caracteres_totales` incluye los caracteres sin nivel HSK; `por_nivel_hsk`
  solo cuenta los clasificados.
- Las definiciones vienen en inglés, como en el dataset de Make Me a Hanzi.

```bash
curl -s "http://localhost/api/v2/publico/resumen/?lang=es"
```

```json
{"sistema": "HanziMentor", "caracteres_totales": 696,
 "por_nivel_hsk": {"1": 83, "2": 71, "3": 92, "4": 117, "5": 183, "6": 150},
 "caracter_del_dia": {"hanzi": "糖", "pinyin": "táng", "definicion": "candy, sugar, sweets", "nivel_hsk": 3},
 "generado_en": "2026-10-26T21:11:29Z"}
```

`lang` distinto de `es` o `en`, o `nivel` fuera de 1 a 6, responde 400
`ENTRADA_INVALIDA`:

```bash
curl -s "http://localhost/api/v2/publico/resumen/?lang=en&nivel=9"
# {"error":"The field 'nivel' must be an integer between 1 and 6","codigo":"ENTRADA_INVALIDA"}
```

Si `flask_catalogo` está caído, el 502 lo arma Nginx (`infra/nginx/nginx.conf`)
y no lleva CORS: desde un navegador el aliado no puede leer ese error, solo ve
que la petición falló. Desde un backend sí lo recibe completo.

### `GET /health`

```bash
curl -s http://localhost:5081/health
# {"estado":"ok","servicio":"catalogo-flask"}
# Si la base no responde: 503 {"estado":"error","servicio":"catalogo-flask","codigo":"DB_NO_DISPONIBLE"}
```

### Errores

Siempre `{"error": "<mensaje>", "codigo": "<CODIGO>"}`:

| Estado | `codigo`              | Cuándo                                                 |
|--------|-----------------------|--------------------------------------------------------|
| 400    | `ENTRADA_INVALIDA`    | `limite` o `nivel` inválidos, cuerpo de lección inválido |
| 404    | `NO_ENCONTRADO`       | Carácter o lección inexistente, o ruta inexistente     |
| 405    | `METODO_NO_PERMITIDO` | Método HTTP no soportado                               |
| 500    | `ERROR_INTERNO`       | Error inesperado (sin stack trace)                     |

Diferencias con v1, todas en los errores:

- `limite` no numérico o negativo: v1 respondía 500, acá 400.
- `nivel` no numérico: v1 respondía 500, acá 400.
- Los 404 traen el mismo mensaje que v1 y además `codigo`.
- Un cuerpo inválido en `generar`: v1 devolvía el dict de errores de DRF por
  campo; acá un único `error` con el campo en el mensaje.

## Docker

```bash
docker build -t catalogo-flask services/catalogo-flask
docker run --rm -p 5081:5000 \
  -v "$PWD/services/contenido/data_hanzi:/datos:ro" catalogo-flask
```

Al arrancar, `docker-entrypoint.sh` busca el dataset en `/datos` (o
`/datos/makemeahanzi`) y lo carga con `--si-vacia`, como hace `contenido`.
Sin el volumen el servicio arranca igual, con la base vacía.
