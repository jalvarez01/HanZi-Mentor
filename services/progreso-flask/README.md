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
| `dominio/progreso.py`| Reglas de acierto, error, historial de errores, agenda de repaso, curva de olvido y desbloqueo de nivel |
| `dominio/curva_olvido.py` | SM-2 con factor de facilidad y respuesta a calidad (RF-IA-02) |
| `dominio/repaso.py`  | Tasa de acierto y los intervalos fijos anteriores (para el estado inicial de la curva) |
| `dominio/codigos.py` | Códigos de error aceptados (RF-IA-01)                             |
| `dominio/patrones.py`| `detectar_patron_error()`: patrones de error (RF-IA-01)           |
| `repositorio.py`     | Acceso a datos y el resumen que devuelve la API                   |
| `servicio.py`        | Casos de uso: consultar, registrar respuesta y error de trazo, refuerzos, patrones |
| `validacion.py`      | UUID, cuerpos de respuesta y de error, y `limite` (400 `ENTRADA_INVALIDA`) |
| `serializacion.py`   | Fechas en ISO 8601 con `Z`, igual que DRF, y la forma de un patrón |
| `rutas.py`           | Blueprint con los siete endpoints                                 |
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
| `tutor/domain/repaso.py`          | `dominio/repaso.py`; el agendado (`calcular_proximo_repaso`) lo reemplaza `dominio/curva_olvido.py` (RF-IA-02) |
| progreso en `ResponderEjercicioService` | `servicio.registrar_respuesta`     |

`ProgresoUsuario` conserva `registrar_error()` y `registrar_acierto()`
como atajos a las reglas del dominio, y suma `detectar_patron_error()`
(RF-IA-01) y `actualizar_curva_olvido()` (RF-IA-02). Ninguno guarda: el
commit lo hace el servicio.

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
2. Se crean las tablas una sola vez, antes de que arranquen los workers
   (incluida `sesiones_aplicadas`, de RF-IA-02), y se agregan a
   `progresos` las columnas que le falten (ver "Migración").
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

`proximo_repaso` es siempre la fecha más cercana de la agenda de repasos
(RF-IA-02). Se calcula al leer, desde `agenda_repaso`, y no desde la columna
del mismo nombre: antes la columna solo cambiaba si la fecha nueva era
anterior, así que cuando un carácter pasaba, por ejemplo, de 12 horas a 1
día, quedaba una fecha vieja que nunca se corregía (el mismo defecto de
v1). En `db_progreso` había 11 filas así. La columna se recalcula cada vez
que se aplica la curva de olvido.

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

Diferencia con v1 (RF-IA-02): **no agenda el repaso.** No toca
`agenda_repaso` ni `proximo_repaso`; la agenda la escribe la curva de
olvido al cerrar la sesión (`POST .../curva-olvido/`). Un usuario que
todavía no cerró ninguna sesión tiene `proximo_repaso` en `null`. Lo único
de la curva que pasa acá es la inicialización perezosa (ver "Curva de
olvido").

Responde `200` con el progreso actualizado, en la misma forma que el GET:

```bash
curl -s -X POST http://localhost:5083/api/v2/progreso/3fa85f64-5717-4562-b3fc-2c963f66afa6/respuestas/ \
  -H "Content-Type: application/json" -d '{"caracter": "学", "acerto": false}'
```

```json
{"usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "nivel_hsk": 1, "nivel_max_desbloqueado": 1,
 "tasa_acierto": 0.45, "caracteres_dominados": [], "errores_frecuentes": {"学": 1},
 "aciertos_consecutivos": {"学": 0}, "proximo_repaso": null,
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

### `POST /api/v2/progreso/<usuario_id>/curva-olvido/`

Uso interno (RF-IA-02): lo llama `flask_sesiones` cuando una sesión se
cierra. Aplica la curva de olvido a cada carácter respondido en esa sesión
y agenda su próximo repaso. Es el `actualizarCurvaOlvido()` del requisito.

Cuerpo:

```json
{"sesion_id": 201, "cerrada_en": "2026-11-10T12:00:00+00:00",
 "respuestas": [{"caracter": "学", "acerto": true},
                {"caracter": "校", "acerto": false, "codigo_error": "PINYIN_FINAL"},
                {"caracter": "人", "acerto": false, "codigo_error": "NO_SABE"},
                {"caracter": "学", "acerto": true}]}
```

| Campo         | Regla                                                                   |
|---------------|-------------------------------------------------------------------------|
| `sesion_id`   | Entero positivo (no `true`, no `"7"`)                                   |
| `cerrada_en`  | Fecha ISO 8601 **con zona horaria**: la fecha de la última respuesta. Los repasos se cuentan desde acá, no desde que llega la petición |
| `respuestas`  | Lista de 1 a 20 objetos `{caracter, acerto, codigo_error}`, con las mismas reglas que `respuestas/`: `caracter` de 1 a 8, `acerto` booleano y `codigo_error` opcional, uno de los 14 códigos (con `acerto: true` se ignora) |

Cualquier otra cosa responde 400 `ENTRADA_INVALIDA`, en español o en inglés
según `Accept-Language`, y no guarda nada. Un usuario sin progreso pasa a
tenerlo, con los valores iniciales. No cambia la racha, la tasa, los
dominados ni los errores: solo `curva_olvido`, `agenda_repaso` y
`proximo_repaso`.

Respuesta, la primera vez: `200` con un repaso por carácter, en el orden
de la sesión. 学 aparece dos veces en la sesión y se agenda una sola vez.

```json
{"usuario_id": "bbbbbbbb-0004-4000-8000-00000000b004", "sesion_id": 201, "aplicada": true,
 "repasos": [
   {"caracter": "学", "proximo_repaso": "2026-11-11T12:00:00Z", "intervalo_dias": 1, "repeticiones": 1},
   {"caracter": "校", "proximo_repaso": "2026-11-11T00:00:00Z", "intervalo_dias": 0, "repeticiones": 0},
   {"caracter": "人", "proximo_repaso": "2026-11-11T00:00:00Z", "intervalo_dias": 0, "repeticiones": 0}]}
```

**Idempotente.** La tabla `sesiones_aplicadas` guarda cada sesión aplicada,
con clave primaria (`usuario_id`, `sesion_id`). La misma sesión otra vez,
aunque llegue con otras respuestas u otra fecha, responde `200` sin cambiar
nada:

```json
{"usuario_id": "bbbbbbbb-0004-4000-8000-00000000b004", "sesion_id": 201, "aplicada": false, "repasos": []}
```

Si dos llamadas de la misma sesión llegan a la vez, la clave primaria hace
fallar a la segunda, que se reintenta, ve la sesión aplicada y responde
`aplicada: false`. Se probó con dos hilos sobre PostgreSQL: una sola fila
en `sesiones_aplicadas`.

### `GET /api/v2/progreso/<usuario_id>/repasos/?dias=7&limite=20`

Repasos agendados del estudiante (RF-IA-02). Lo usan `flask_sesiones`, para
poner primero los vencidos, y la sección "Próximos repasos" de Progreso.

| Parámetro | Rango   | Por defecto | Uso                                        |
|-----------|---------|-------------|--------------------------------------------|
| `dias`    | 1 a 30  | 7           | Hasta cuántos días adelante entra en `proximos` |
| `limite`  | 1 a 50  | 20          | Máximo de cada lista, por separado         |

```json
{"usuario_id": "bbbbbbbb-0004-4000-8000-00000000b004", "momento": "2026-11-11T01:21:28.515261Z", "dias": 7,
 "vencidos": [{"caracter": "人", "proximo_repaso": "2026-11-11T00:00:00Z", "intervalo_dias": 0, "repeticiones": 0},
              {"caracter": "校", "proximo_repaso": "2026-11-11T00:00:00Z", "intervalo_dias": 0, "repeticiones": 0}],
 "proximos": [{"caracter": "学", "proximo_repaso": "2026-11-17T12:00:00Z", "intervalo_dias": 6, "repeticiones": 2}]}
```

- `vencidos`: fecha igual o anterior a `momento`, del más atrasado al menos
  atrasado.
- `proximos`: después de `momento` y hasta `dias` días, del más cercano al
  más lejano.
- Un usuario sin progreso recibe las dos listas vacías y no se guarda nada.
- Un carácter agendado con el algoritmo anterior aparece con su fecha de
  siempre y con `intervalo_dias` y `repeticiones` derivados de su racha.

## Curva de olvido (RF-IA-02)

### SM-2 con factor de facilidad

Función pura `actualizar_curva_olvido(estado, calidad, momento)` en
`dominio/curva_olvido.py`. Estado por carácter, en la columna
`curva_olvido`: `{facilidad, repeticiones, intervalo_dias}`. La fecha sigue
en `agenda_repaso`.

- **Facilidad:** empieza en 2.5 y nunca baja de 1.3. Se actualiza en toda
  respuesta, también en un fallo:
  `facilidad + 0.1 - (5 - q) x (0.08 + (5 - q) x 0.02)`. Así un carácter que
  cuesta queda con intervalos más cortos.
- **Acierto (calidad 3 o más):** `repeticiones + 1`. El intervalo es 1 día
  en la primera repetición, 6 en la segunda y después
  `round(intervalo x facilidad)`, con la facilidad anterior a esta
  respuesta (SM-2 clásico).
- **Fallo (calidad menor que 3):** `repeticiones` 0, `intervalo_dias` 0 y el
  próximo repaso a las 12 horas, el mismo intervalo corto que ya existía.
- **Redondeo:** la mitad hacia arriba (12.5 da 13, 17.5 da 18), no el
  redondeo bancario de `round()` de Python, que daría 12.

| Calidad | Cambio de la facilidad |
|---------|------------------------|
| 5       | +0.10                  |
| 4       | 0                      |
| 3       | -0.14                  |
| 2       | -0.32                  |
| 1       | -0.54                  |
| 0       | -0.80                  |

### De la respuesta a la calidad

| Respuesta                                                              | Calidad | Por qué |
|------------------------------------------------------------------------|---------|---------|
| Acierto                                                                | 4       | Correcto. Ninguna llega a 5: no se mide el tiempo de respuesta ni el tono |
| `PINYIN_INICIAL`, `PINYIN_FINAL`, `SIGNIFICADO_PARCIAL`, `SIGNIFICADO_CERCANO` | 2 | Fallo cercano: recordaba una parte |
| `PINYIN_DISTINTO`, `SIGNIFICADO_DISTINTO`, `TRAZO_AUTOCALIFICADO`, fallo sin código | 1 | Fallo, pero lo reconocía |
| `NO_SABE`                                                              | 0       | No lo recordaba en absoluto |

Un código que no está en la tabla (por ejemplo, un `TRAZO_*` evaluado, que
solo sale de la página Trazos y no llega a una sesión) cuenta como fallo
sin código.

Si un carácter aparece varias veces en la sesión, se actualiza **una sola
vez, con su peor calidad**: un fallo dice que todavía no está consolidado.
La curva se aplica a **todos** los caracteres respondidos en la sesión: los
dominados alargan su intervalo y los fallados lo acortan.

### Ejemplo calculado a mano

Un carácter nuevo; cada fila es una sesión cerrada a las 12:00
(`tests/test_curva_olvido.py` lo comprueba).

| Sesión | Calidad | Facilidad | Repeticiones | Intervalo | Próximo repaso |
|--------|---------|-----------|--------------|-----------|----------------|
| 1      | 4       | 2.5       | 1            | 1 día     | +1 día         |
| 2      | 4       | 2.5       | 2            | 6 días    | +6 días        |
| 3      | 4       | 2.5       | 3            | `round(6 x 2.5)` = 15 días | +15 días |
| 4      | 2       | 2.18      | 0            | 0         | +12 horas      |
| 5      | 4       | 2.18      | 1            | 1 día     | +1 día         |

### Caracteres con agenda anterior: inicialización perezosa

Los caracteres que ya tenían fecha en `agenda_repaso` con el algoritmo
anterior no se migran: la migración no reescribe filas y ninguna fecha
agendada se pierde.

- La primera vez que un carácter así se responde (`POST .../respuestas/`),
  se le fija el estado SM-2 con la racha **de antes de responder**:
  facilidad 2.5, `repeticiones` = la racha e `intervalo_dias` = el que le
  daba el algoritmo anterior a esa racha (1, 3, 7, 16, 35 o 90 días; 0 si
  la racha es 0). Ejemplo: racha 3 da intervalo 7, y el siguiente acierto,
  `round(7 x 2.5)` = 18 días.
- Se hace en la respuesta y no al cerrar porque, al cerrar, la racha ya
  incluye las respuestas de esa sesión.
- Su fecha de `agenda_repaso` no cambia hasta que se aplica la curva de una
  sesión donde se respondió.
- Una sesión que empezó antes del despliegue puede llegar al cierre sin ese
  estado fijado: entonces se usa la racha actual, que es una aproximación.

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
`progresos` las columnas que le falten:

```sql
-- RF-IA-01
ALTER TABLE progresos ADD COLUMN IF NOT EXISTS errores_por_codigo JSON NOT NULL DEFAULT '{}';
ALTER TABLE progresos ADD COLUMN IF NOT EXISTS historial_errores JSON NOT NULL DEFAULT '[]';
-- RF-IA-02
ALTER TABLE progresos ADD COLUMN IF NOT EXISTS curva_olvido JSON NOT NULL DEFAULT '{}';
```

La tabla `sesiones_aplicadas` (RF-IA-02) es nueva: la crea `create_all`.

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

Cada migración se probó sobre una copia de `db_progreso` hecha con
`pg_dump`, antes de aplicarla a la base real:

| Requisito | Filas | Primera ejecución | Segunda ejecución | Huella md5 de las columnas anteriores |
|-----------|-------|-------------------|-------------------|---------------------------------------|
| RF-IA-01  | 20    | Agregó `errores_por_codigo` e `historial_errores` | Sin cambios | Idéntica (11 columnas) |
| RF-IA-02  | 23    | Agregó `curva_olvido` y creó `sesiones_aplicadas` | Sin cambios | Idéntica (13 columnas) |

En RF-IA-02 se respaldaron antes `db_progreso` y `db_sesiones` con
`pg_dump`, y después del despliegue la huella de las filas anteriores de
la base real siguió idéntica. `tests/test_migraciones.py` repite la prueba
en SQLite: desde el esquema original y desde el de RF-IA-01.

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
| 400    | `ENTRADA_INVALIDA`    | UUID inválido, cuerpo inválido, `codigo_error` desconocido (o que no es de trazo en `errores/`), `limite` o `dias` fuera de rango, o un cuerpo de `curva-olvido/` que no cumple sus reglas |
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
