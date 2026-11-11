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
| `migraciones.py`     | Columnas nuevas sobre una tabla que ya existe (idempotente)       |
| `modelos.py`         | `ProgresoUsuario` y el tipo `FechaUTC`                            |
| `dominio/progreso.py`| Reglas de acierto, error, historial de errores, agenda de repaso y desbloqueo de nivel |
| `dominio/repaso.py`  | Repaso espaciado (SM-2 simplificado) y tasa de acierto            |
| `dominio/codigos.py` | Códigos de error aceptados (RF-IA-01)                             |
| `dominio/patrones.py`| `detectar_patron_error()`: patrones de error (RF-IA-01)           |
| `repositorio.py`     | Acceso a datos y el resumen que devuelve la API                   |
| `servicio.py`        | Casos de uso: consultar, registrar respuesta y error de trazo, refuerzos, patrones |
| `validacion.py`      | UUID, cuerpos de respuesta y de error, y `limite` (400 `ENTRADA_INVALIDA`) |
| `serializacion.py`   | Fechas en ISO 8601 con `Z`, igual que DRF, y la forma de un patrón |
| `rutas.py`           | Blueprint con los cinco endpoints                                 |
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
como atajos a las reglas del dominio, y suma `detectar_patron_error()`
(RF-IA-01). Ninguno guarda: el commit lo hace el servicio.

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
2. Se crean las tablas una sola vez, antes de que arranquen los workers, y
   se agregan a `progresos` las columnas que le falten (ver "Migración").
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

Uso interno: lo llama `flask_sesiones` (T12) en vez de tocar estas tablas.
Cuerpo: `{"caracter": "学", "acerto": true}` (`caracter` de 1 a 8
caracteres, `acerto` booleano) y, opcional, `codigo_error` (RF-IA-01):

- `codigo_error` es el tipo de error de un fallo: uno de los 14 códigos de
  "Patrones de error". Ausente o `null`, el fallo se guarda sin código,
  como antes. Un texto fuera de la lista o un valor que no es texto
  responde 400 `ENTRADA_INVALIDA` y no guarda nada. Con `acerto: true` se
  ignora sin revisarlo.
- Un fallo se agrega al historial reciente (con su código, si lo tiene) y
  suma a su código en `errores_por_codigo`. La respuesta no cambia de forma.

Aplica las mismas reglas que v1:

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

### `POST /api/v2/progreso/<usuario_id>/errores/`

Uso de la página Trazos (RF-IA-01), que es práctica libre fuera de una
sesión. Anota el tipo de error de un trazo fallado para los patrones de
error. Cuerpo: `{"caracter": "人", "codigo_error": "TRAZO_INVERTIDO"}`.

- Solo acepta los seis códigos `TRAZO_*` que devuelve evaluacion-flask.
  `TRAZO_AUTOCALIFICADO`, `NO_SABE` y los de pinyin o significado
  responden 400.
- No cambia la racha, los dominados, los errores frecuentes, la tasa de
  acierto ni el repaso: solo el historial y `errores_por_codigo`.
- El mismo carácter con el mismo código en menos de 2 minutos es un
  reintento del mismo trazo y cuenta una sola vez: responde 200 con
  `"registrado": false`.
- Un usuario sin progreso pasa a tenerlo, con los valores iniciales.

```bash
curl -s -X POST http://localhost:5083/api/v2/progreso/3fa85f64-5717-4562-b3fc-2c963f66afa6/errores/ \
  -H "Content-Type: application/json" -d '{"caracter": "人", "codigo_error": "TRAZO_INVERTIDO"}'
# {"usuario_id":"3fa85f64-5717-4562-b3fc-2c963f66afa6","registrado":true}
```

### `GET /api/v2/progreso/<usuario_id>/patrones/`

Patrones de error del estudiante (RF-IA-01), del más relevante al menos
relevante. Un usuario sin progreso, o sin fallos suficientes, recibe
`"patrones": []` y no se guarda nada. `titulo` y `consejo` salen en el
idioma de `Accept-Language`; el resto no cambia con el idioma.

```json
{"usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "ventana_dias": 14,
 "patrones": [
   {"codigo": "PATRON_TRAZO_INVERTIDO", "tipo": "error", "frecuencia": 3,
    "caracteres": ["水", "大", "人"], "ultima_vez": "2026-11-10T03:09:26.141603Z",
    "titulo": "Trazos al revés",
    "consejo": "Antes de trazar, mirá dónde empieza el modelo: casi siempre es de arriba hacia abajo y de izquierda a derecha."}]}
```

| Campo        | Contenido                                                        |
|--------------|------------------------------------------------------------------|
| `codigo`     | Código estable del patrón (ver la tabla de abajo)                |
| `tipo`       | `error` (un tipo de error se repite) o `caracter` (un carácter)  |
| `frecuencia` | Fallos de la ventana que forman el patrón                        |
| `caracteres` | Hasta 5, del más fallado al menos fallado                        |
| `ultima_vez` | Fecha del fallo más reciente del patrón                          |

## Patrones de error (RF-IA-01)

### Qué se guarda

Dos columnas de `ProgresoUsuario`:

- `errores_por_codigo`: código de error -> total acumulado. No se descuenta
  al acertar, a diferencia de `errores_frecuentes`.
- `historial_errores`: los últimos 50 fallos de cada origen, `sesion`
  (Práctica, uno por ejercicio) y `trazos` (página Trazos, uno por trazo).
  Cada fallo es `{codigo, caracter, fecha, origen, dominado}`, donde
  `dominado` dice si el carácter estaba dominado justo antes de fallar. El
  tope es por origen para que una tarde en Trazos no saque del historial
  los fallos de sesión.

Los 14 códigos aceptados (`dominio/codigos.py`) son los 12
`explicacion.codigo` de evaluacion-flask más dos de Práctica, donde no hay
evaluación del servicio: `TRAZO_AUTOCALIFICADO` ("Fallé" en un trazo) y
`NO_SABE` ("No lo sé"). `tests/test_codigos.py` compara la lista con
`services/evaluacion-flask/adaptadores/reglas.py`.

### `detectar_patron_error()`

Función pura de `dominio/patrones.py`: recibe el historial y el momento
actual, y no lee ni guarda nada. Se calcula al consultar `patrones/`.

Patrones por tipo de error (`tipo: "error"`), con los fallos de sesión y de
Trazos:

| Familia     | Patrón                   | Códigos que lo alimentan                          |
|-------------|--------------------------|---------------------------------------------------|
| trazo       | `PATRON_TRAZO_INVERTIDO` | `TRAZO_INVERTIDO`                                 |
| trazo       | `PATRON_TRAZO_LONGITUD`  | `TRAZO_CORTO`, `TRAZO_LARGO`, `TRAZO_INCOMPLETO`  |
| trazo       | `PATRON_TRAZO_POSICION`  | `TRAZO_FUERA_DE_LUGAR`                            |
| trazo       | `PATRON_TRAZO_FORMA`     | `TRAZO_IMPRECISO`                                 |
| pinyin      | `PATRON_PINYIN_INICIAL`  | `PINYIN_INICIAL`                                  |
| pinyin      | `PATRON_PINYIN_FINAL`    | `PINYIN_FINAL`                                    |
| pinyin      | `PATRON_PINYIN_LECTURA`  | `PINYIN_DISTINTO`                                 |
| pinyin      | `PATRON_NO_SABE`         | `NO_SABE`                                         |
| significado | `PATRON_SIGNIFICADO`     | `SIGNIFICADO_PARCIAL`, `SIGNIFICADO_CERCANO`, `SIGNIFICADO_DISTINTO` |

Patrones por carácter (`tipo: "caracter"`), solo con fallos de sesión:

- `PATRON_CARACTER_RECURRENTE`: el mismo carácter falla 3 veces o más. Lo
  alimenta cualquier fallo, con código o sin él.
- `PATRON_RETROCESO`: 3 fallos o más sobre caracteres que estaban
  dominados.

Los fallos de Trazos no cuentan para estos dos: allí hay un fallo por
trazo, y un carácter de muchos trazos inflaría la cuenta.
`TRAZO_AUTOCALIFICADO` y los fallos sin código no forman ningún patrón de
tipo, porque no dicen qué falló, pero sí cuentan para los de carácter.

Umbrales:

| Constante           | Valor | Por qué                                                         |
|---------------------|-------|-----------------------------------------------------------------|
| `VENTANA_DIAS`      | 14    | Un carácter fallado vuelve entre 12 horas y 7 días después: una debilidad real se repite dentro de la ventana, y una ya corregida deja de aparecer |
| `MIN_OCURRENCIAS`   | 3     | Un fallo es un descuido y dos pueden ser coincidencia           |
| `PROPORCION_MINIMA` | 0.30  | Solo en los de tipo `error`: ocurrencias sobre los fallos de la misma familia en la ventana. Supera el 25 % de un reparto parejo entre los cuatro patrones de una familia |
| `HISTORIAL_MAXIMO`  | 50    | Fallos guardados por origen; acota el JSON a unos 9 KB por usuario |

La proporción se mide contra la familia para que mucha práctica de trazos
no esconda un patrón de pinyin. Ejemplo: 3 trazos al revés entre 10 fallos
de trazo es un patrón (30 %); entre 11, no (27 %).

Ventana: cuenta un fallo con fecha igual o posterior a `momento - 14 días`.
Una entrada del historial mal formada (sin carácter, con una fecha que no
se puede leer) se ignora.

Orden: por `frecuencia` descendente, después por `ultima_vez` más reciente
y después por `codigo`, así la misma entrada da siempre la misma lista.
Práctica muestra el primero en su aviso de fin de sesión.

`PATRON_SIGNIFICADO` está implementado y probado, pero hoy no puede
aparecer: Práctica evalúa como pinyin los ejercicios que no son de trazo,
así que ningún código `SIGNIFICADO_*` llega al historial.

Los textos (`titulo`, `consejo`) están en `dominio/patrones.py` con `N_` y
en los `.po` de `translations/`: un título corto y un consejo con una sola
idea.

## Migración

`create_all` crea las tablas que faltan pero no altera una tabla que ya
existe. Para una base con datos, `migraciones.aplicar()` agrega a
`progresos` las columnas de RF-IA-01:

```sql
ALTER TABLE progresos ADD COLUMN IF NOT EXISTS errores_por_codigo JSON NOT NULL DEFAULT '{}';
ALTER TABLE progresos ADD COLUMN IF NOT EXISTS historial_errores JSON NOT NULL DEFAULT '[]';
```

- La llama `iniciar_db` en cada arranque, después de `create_all`.
- Es idempotente: primero consulta qué columnas faltan y, si no falta
  ninguna, no hace nada. En PostgreSQL, `IF NOT EXISTS` cubre además el
  caso de dos workers que arrancan a la vez; SQLite no lo admite y no lo
  necesita.
- No pierde datos: las filas existentes toman el valor por defecto, y en
  PostgreSQL 11 o superior agregar una columna con un valor constante no
  reescribe la tabla.
- El valor por defecto queda en la base, así que una imagen anterior del
  servicio puede seguir insertando filas si hay que volver atrás.
  `modelos.py` declara el mismo `server_default`: una base nueva y una
  migrada tienen el mismo esquema.

Se probó sobre una copia de `db_progreso` hecha con `pg_dump` (20 filas):
la primera ejecución agregó las dos columnas, la segunda no hizo nada, y
la cantidad de filas y una huella md5 de las 11 columnas anteriores fueron
idénticas antes y después. `tests/test_migraciones.py` repite la prueba en
SQLite con el esquema anterior.

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
| 400    | `ENTRADA_INVALIDA`    | UUID inválido, cuerpo inválido, `codigo_error` desconocido (o que no es de trazo en `errores/`) o `limite` fuera de rango |
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
