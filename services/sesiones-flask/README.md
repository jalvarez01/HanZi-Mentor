# sesiones-flask

Microservicio Flask de las sesiones de estudio adaptativas (tarea T12 del
Strangler Pattern). Reemplaza en `/api/v2/` a las sesiones y respuestas de
`services/agente-tutor` (app `tutor`). Tiene su propia base de datos, no
importa código de otros servicios y no lee sus bases: lo que necesita de
catalogo-flask y progreso-flask lo pide por HTTP. v1
(`/api/v1/tutor/sesiones/`) sigue funcionando mientras conviven las dos
versiones (T17).

Sigue el estándar de [`docs/arquitectura/estandar-flask.md`](../../docs/arquitectura/estandar-flask.md)
y parte de la plantilla `services/flask-base`.

## Estructura

| Archivo                | Responsabilidad                                                  |
|------------------------|------------------------------------------------------------------|
| `app.py`               | Fábrica `create_app()`: config, base, errores, dependencias, rutas |
| `config.py`            | Configuración desde variables de entorno                         |
| `db.py`                | SQLAlchemy 2.x: `Base`, sesión por petición, chequeo de conexión |
| `migraciones.py`       | Columnas nuevas sobre una tabla que ya existe (idempotente, RF-IA-02) |
| `modelos.py`           | `SesionEstudio` y `Ejercicio`                                    |
| `dominio/builder.py`   | `SesionEstudioBuilder` con las validaciones de v1, vencidos y sin caracteres repetidos |
| `dominio/sesion.py`    | Ciclo de vida: pendientes y cierre de la sesión                  |
| `dominio/desempeno.py` | Desempeño de una sesión terminada: duración, fecha y resultados (RF-IA-05) |
| `dominio/repaso.py`    | Intervalos fijos para la estimación de `proximo_repaso` que devuelve responder |
| `dominio/excepciones.py` | Errores de negocio con su estado HTTP y su código              |
| `dominio/codigos_error.py` | Códigos que acepta `codigo_error` al responder (RF-IA-01)    |
| `clientes.py`          | Cliente HTTP resiliente y clientes de catálogo y progreso        |
| `motores.py`           | `MotorTutor` y `MotorTutorMock` (dificultad, caracteres nuevos y ejercicios adaptados) |
| `dominio/adaptacion.py` | Ejercicios dirigidos a un patrón de error (RF-IA-03)            |
| `notificadores.py`     | `Notificador` y los adaptadores de consola y de cola (Celery)    |
| `fabricas.py`          | Elige motor, notificador y clientes según la configuración       |
| `repositorio.py`       | Acceso a la base; guarda sesión y ejercicios en una transacción  |
| `servicio.py`          | `SesionEstudioService` y `ResponderEjercicioService`             |
| `validacion.py`, `serializacion.py`, `rutas.py` | Entrada, JSON igual a v1 y los endpoints |
| `crear_base.py`, `docker-entrypoint.sh` | Base en el PostgreSQL compartido, igual que progreso-flask |

Equivalencias con v1 (`services/agente-tutor/tutor`):

| Django                              | Flask                                     |
|-------------------------------------|-------------------------------------------|
| `models.py`                         | `modelos.py`                              |
| `domain/builders.py`                | `dominio/builder.py`                      |
| `domain/sesion_logic.py`            | `dominio/sesion.py`                       |
| `services.py` (sesión y respuesta)  | `servicio.py`                             |
| `infra/motores.py` (MotorTutorMock) | `motores.py`                              |
| `infra/notificadores.py` (consola)  | `notificadores.py`                        |
| `infra/factories.py`                | `fabricas.py`                             |
| `infra/catalogo.py`, `ProgresoRepository` | `clientes.py` (por HTTP)            |

El Builder no usa el ORM directamente: `build(repositorio)` valida todo y
recién entonces llama a `repositorio.guardar_sesion()`, que guarda la sesión
y sus ejercicios en una sola transacción.

### Composición de una sesión (RF-IA-02 y RF-IA-03)

`SesionEstudioService` arma la sesión en este orden, sin repetir ningún
carácter entre los grupos ni dentro de uno:

| Orden | Grupo     | Cuántos | De dónde | Tipo | `es_refuerzo` |
|-------|-----------|---------|----------|------|---------------|
| 1     | Vencidos  | Hasta 4 | `GET .../repasos/?limite=4` de progreso-flask, del más atrasado al menos atrasado | `significado` | true |
| 2     | Adaptados | Hasta 3 | `GET .../patrones/`: los patrones de error, del más relevante al menos | según el patrón | true |
| 3     | Refuerzos | Lo que dejan libre los adaptados del cupo de 3 | `GET .../refuerzos/`: los caracteres con más fallos | `trazo` | true |
| 4     | Nuevos    | Hasta completar 7, con al menos 1 | Catálogo, sin los dominados | `significado` | false |

- Adaptados y refuerzos comparten un cupo de 3, con los adaptados
  primero: 3 adaptados dejan 0 refuerzos, 1 adaptado deja hasta 2 y sin
  adaptados (por ejemplo, con progreso caído) son hasta 3 refuerzos, como
  en RF-IA-02.
- Sin vencidos, adaptados ni refuerzos son 7 nuevos; con 4 vencidos y el
  cupo de 3 lleno va 1 nuevo, así que una sesión tiene de 7 a 8 ejercicios,
  el máximo de RF-IA-02 (menos si el catálogo no alcanza; el mínimo del
  Builder sigue siendo 3).
- Un carácter que está en dos grupos aparece una sola vez, en el primero. Cada grupo se pide con margen
  (uno de más por cada carácter ya elegido) para completar su cantidad
  después de quitar los repetidos. Antes de RF-IA-02 un refuerzo podía
  repetirse como nuevo.
- Los vencidos son lo que hace volver a los caracteres dominados: el motor
  los excluye de los nuevos, así que sin la curva de olvido un carácter
  dominado no volvía a practicarse.
- Los vencidos son de tipo `significado` para que Práctica los evalúe en el
  servidor (como pinyin), y llevan `es_refuerzo` true porque son repasos.

### Ejercicios adaptativos (RF-IA-03)

Cuando progreso-flask detecta un patrón de error (RF-IA-01), el tutor
ejecuta `generar_ejercicio_adaptado(patron, dificultad, cantidad)`
(`generarEjercicioAdaptado(p)` del diagrama) y la sesión incluye ejercicios
dirigidos a esa debilidad. La lógica es pura y está en
`dominio/adaptacion.py`; `MotorTutor` la expone como método para que otro
motor pueda redefinirla.

| Patrón | Ejercicio |
|--------|-----------|
| `PATRON_TRAZO_INVERTIDO`, `_LONGITUD`, `_POSICION`, `_FORMA` | `trazo` |
| `PATRON_PINYIN_INICIAL`, `_FINAL`, `_LECTURA`, `PATRON_NO_SABE` | `pinyin` |
| `PATRON_SIGNIFICADO` | `significado` |
| `PATRON_CARACTER_RECURRENTE` | `trazo` (el consejo del patrón es practicarlo en Trazos) |
| `PATRON_RETROCESO` | `pinyin` (la lectura es lo primero que se olvida) |

- Los caracteres son los del patrón, en su orden. Si el primer patrón no
  alcanza para 3, se completa con los siguientes; un carácter queda con el
  patrón más relevante que lo nombra.
- Van después de los vencidos y antes de los refuerzos: un carácter que
  falla seguido suele ser también refuerzo, y así se practica con el tipo
  de ejercicio que ataca su error y no siempre con trazo.
- La dificultad baja un punto (mínimo 1): es justo lo que le cuesta al
  estudiante, así que empieza un paso más fácil que el resto.
- Cada ejercicio guarda el código del patrón en la columna `patron` y lo
  devuelve en el JSON (ver "Contrato"). Los demás quedan con `null`.
- Un patrón con un código que no está en la tabla no genera nada, y
  `tests/test_adaptacion.py` comprueba que la tabla cubre los once códigos
  de `progreso-flask/dominio/patrones.py`.

## Motor y notificador

- `TUTOR_ENGINE`: solo `MOCK`. El motor con LangGraph sigue en agente-tutor
  porque depende del agente y de sus credenciales. Cualquier otro valor hace
  fallar el arranque con un mensaje claro.
- `NOTIFICADOR`:
  - `consola` (por defecto; `console` también vale): deja una línea en el log.
  - `cola`: publica la tarea `notificar_sesion_lista(usuario_id, sesion_id)`
    en Redis (`REDIS_URL`) para el worker de `reportes-flask`, que la guarda
    en `GET /api/v2/reportes/notificaciones/<usuario_id>/`. Publica por
    **nombre** con `send_task`, sin importar código de reportes-flask, con
    una app Celery propia sin backend de resultados, sin reintentos y con
    timeouts de 1 s. En Docker es el valor que usa `flask_sesiones`.

  Publica en un hilo aparte y la respuesta no lo espera: con el contenedor
  de Redis detenido, solo resolver el nombre `redis` tarda varios segundos y
  los timeouts de conexión no cubren el DNS.

  - Un hilo **daemon** por proceso de gunicorn, creado en la primera sesión
    de ese proceso (después del fork, nunca al importar ni en el maestro).
    El `CMD` del Dockerfile no usa `--preload`; si se agrega, el hilo igual
    se crea en cada worker, porque se detecta el cambio de pid.
  - Cola con límite de 100 pendientes (`queue.Queue(maxsize=100)`); si está
    llena, la notificación se descarta con un aviso en el log.

  **Las notificaciones son de mejor esfuerzo.** Se pierden, con un aviso en
  el log, si Redis está caído al publicar, si la cola del proceso está
  llena o si el proceso se reinicia con trabajos pendientes (también al
  reiniciar Redis, que no guarda nada en disco). En ningún caso cambia la
  respuesta de crear la sesión: siempre 201.

  El de email usaba el backend de correo de Django y no se portó.

## Comunicación con otros servicios (base de T16)

| Servicio      | Variable       | Rutas que usa                                                    |
|---------------|----------------|------------------------------------------------------------------|
| catalogo-flask| `CATALOGO_URL` | `GET /api/v2/caracteres/?nivel=&excluir=&limite=`                |
| progreso-flask| `PROGRESO_URL` | `GET /api/v2/progreso/<id>/`, `GET .../repasos/?limite=4`, `GET .../patrones/`, `GET .../refuerzos/`, `POST .../respuestas/`, `POST .../curva-olvido/` |

Las URL son la base del servicio, sin `/api/v2` (por ejemplo
`http://flask_catalogo:5000`). Todo pasa por `clientes.ClienteHttp`:

- **Timeout** en cada petición: `HTTP_TIMEOUT`, 3 s por defecto.
- **Reintentos** solo en GET: `HTTP_REINTENTOS`, 2 por defecto, con esperas
  de 0.2 s, 0.4 s, etc. Se reintentan errores de red, timeouts, 5xx y
  respuestas que no son JSON. Un 4xx no se reintenta. Un POST nunca se
  reintenta, para no registrar dos veces la misma respuesta.
- **Respuesta degradada** si el servicio no responde:

| Falla                         | Qué hace sesiones-flask                                       |
|-------------------------------|---------------------------------------------------------------|
| Catálogo caído o vacío        | Usa una lista local de 10 caracteres por nivel HSK (la de v1) |
| GET de progreso caído         | Usa los valores iniciales (HSK1, tasa 0.5, sin dominados)     |
| Repasos vencidos caídos       | La sesión se arma sin vencidos                                |
| Patrones de error caídos      | La sesión se arma sin ejercicios adaptados                    |
| Refuerzos caídos              | La sesión se arma sin refuerzos                               |
| POST de respuesta caído       | La respuesta queda guardada en la sesión y se devuelve `aviso` |
| POST de curva de olvido caído | Advertencia en el log; la respuesta no cambia y la sesión queda completada. No se reintenta |

Nunca se devuelve una página HTML: los errores propios del servicio siempre
son JSON. Con progreso caído, un usuario que ya tenía desbloqueado un nivel
alto recibe 400 si pide ese nivel, porque los valores iniciales solo
desbloquean HSK1.

## Ejecutar

```bash
cd services/sesiones-flask
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q

# Con catalogo-flask en 5081 y progreso-flask en 5083 (ver sus README).
# En macOS el puerto 5000 lo usa AirPlay.
CATALOGO_URL=http://127.0.0.1:5081 PROGRESO_URL=http://127.0.0.1:5083 \
  .venv/bin/gunicorn -w 2 -b 127.0.0.1:5086 "app:create_app()"
```

## Variables de entorno

| Variable           | Default                 | Uso                                          |
|--------------------|-------------------------|----------------------------------------------|
| `SERVICE_NAME`     | `sesiones-flask`        | Nombre que devuelve `/health`                |
| `HOST`, `PORT`     | `0.0.0.0`, `5000`       | Interfaz y puerto                            |
| `FLASK_DEBUG`      | `0`                     | `1` activa debug, solo en local              |
| `DATABASE_URL`     | `sqlite:///db.sqlite3`  | URL de SQLAlchemy de la base propia          |
| `DB_CREAR_TABLAS`  | `1`                     | Crea las tablas al arrancar                  |
| `CATALOGO_URL`     | `http://localhost:5081` | URL base de catalogo-flask                   |
| `PROGRESO_URL`     | `http://localhost:5083` | URL base de progreso-flask                   |
| `HTTP_TIMEOUT`     | `3`                     | Segundos por petición a otro servicio        |
| `HTTP_REINTENTOS`  | `2`                     | Reintentos de los GET                        |
| `TUTOR_ENGINE`     | `MOCK`                  | Motor del tutor (solo MOCK)                  |
| `NOTIFICADOR`      | `consola`               | Notificador: `consola` o `cola`              |
| `REDIS_URL`        | `redis://localhost:6379/0` | Broker de Celery (solo con `cola`)        |
| `REDIS_TIMEOUT`    | `1`                     | Segundos de espera al publicar en Redis      |
| `GUNICORN_WORKERS` | `2`                     | Procesos de gunicorn (Docker)                |

## Base de datos en Docker

Mismo esquema que catalogo-flask y progreso-flask: un solo PostgreSQL (`db`)
con una base por servicio. La de este es `db_sesiones`:

`DATABASE_URL=postgresql+psycopg2://hanzimentor:hanzimentor@db:5432/db_sesiones`

Al arrancar, `crear_base.py` crea la base si no existe (si existe, solo lo
informa), se crean las tablas una sola vez, se agregan las columnas que
falten (ver "Migración") y arranca gunicorn. Si PostgreSQL no responde, el
servicio arranca igual y `/health` responde 503.

### Migración

RF-IA-02 trae la primera migración de `db_sesiones`, RF-IA-03 la segunda y
RF-IA-05 suma tres columnas a `sesiones`. `create_all` no altera una tabla
que ya existe, así que `migraciones.aplicar()`, con el mismo patrón que
progreso-flask, agrega las columnas en una base con datos:

```sql
ALTER TABLE ejercicios ADD COLUMN IF NOT EXISTS codigo_error VARCHAR(40);             -- RF-IA-02
ALTER TABLE ejercicios ADD COLUMN IF NOT EXISTS patron VARCHAR(40);                   -- RF-IA-03
ALTER TABLE sesiones ADD COLUMN IF NOT EXISTS completada_en TIMESTAMP WITH TIME ZONE; -- RF-IA-05
ALTER TABLE sesiones ADD COLUMN IF NOT EXISTS duracion_seg INTEGER;                   -- RF-IA-05
ALTER TABLE sesiones ADD COLUMN IF NOT EXISTS aciertos SMALLINT;                      -- RF-IA-05
```

- La llama `iniciar_db` en cada arranque, después de `create_all`.
- Es idempotente: si la columna ya está, no hace nada. En PostgreSQL,
  `IF NOT EXISTS` cubre además el caso de dos workers que arrancan a la vez.
- Las columnas admiten NULL y no tienen valor por defecto: las filas que ya
  existen quedan con NULL y las tablas no se reescriben. Una imagen anterior
  del servicio puede seguir insertando si hay que volver atrás.
- Las sesiones que ya estaban cerradas no se rellenan: su desempeño se
  calcula con la fecha de su última respuesta (ver "Desempeño").

Se probó sobre una copia de `db_sesiones` hecha con `pg_dump` (88 sesiones y
372 ejercicios): la primera ejecución agregó la columna, la segunda y la
tercera no hicieron nada, y la cantidad de filas y una huella md5 de las
columnas anteriores de las dos tablas fueron idénticas antes y después.
Con `patron` se repitió la prueba sobre una base de RF-IA-02 con datos (ver
la descripción del PR).
Antes del despliegue se respaldó la base con `pg_dump`, y después la huella
de la base real siguió idéntica. `tests/test_migraciones.py` repite la
prueba en SQLite con el esquema anterior. Las columnas de RF-IA-05 se
probaron igual, sobre una base de development con datos (ver la descripción
del PR).

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

Las respuestas tienen las mismas claves, en el mismo orden, que los
serializers de agente-tutor (`tests/test_contrato.py` lo comprueba). La
única clave extra es `patron` en cada ejercicio (RF-IA-03), al final.

### `POST /api/v2/sesiones/`

Cuerpo: `usuario_id` (UUID, o un entero como acepta DRF), `nivel_hsk` (1 a
6) y `duracion_min` (5 a 60, por defecto 10). Responde `201`. Primero van los
repasos vencidos, después los adaptados y los refuerzos (ver "Composición de
una sesión"). Cada ejercicio trae al final `patron`, la única clave que v1 no
tiene: el código del patrón de error al que apunta, o `null`. Va al final
para que las claves de v1 conserven su orden.

```json
{"id": 2, "usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "nivel_hsk": 1, "dificultad": 2,
 "estado": "activa", "duracion_estimada_min": 10, "creada_en": "2026-10-23T20:32:45.598104Z",
 "ejercicios": [
   {"id": 5, "caracter": "水", "tipo": "trazo", "dificultad": 1, "es_refuerzo": true, "patron": "PATRON_TRAZO_INVERTIDO"},
   {"id": 6, "caracter": "你", "tipo": "trazo", "dificultad": 2, "es_refuerzo": true, "patron": null},
   {"id": 7, "caracter": "大", "tipo": "significado", "dificultad": 2, "es_refuerzo": false, "patron": null}]}
```

Nivel bloqueado: `400 {"error": "HSK3 aún no está desbloqueado (máximo actual: HSK1).", "codigo": "NIVEL_NO_PERMITIDO"}`,
con el mismo mensaje que v1.

### `GET /api/v2/sesiones/<id>/`

Misma forma que la respuesta de creación.

### `POST /api/v2/ejercicios/<id>/responder/`

Cuerpo: `{"acerto": true}` (acepta los mismos valores que `BooleanField` de
DRF). Marca el ejercicio, cierra la sesión si era el último y registra la
respuesta en progreso-flask.

Opcional, `codigo_error` (RF-IA-01): el tipo de error de un fallo, por
ejemplo `{"acerto": false, "codigo_error": "PINYIN_INICIAL"}`. Lo usa
progreso-flask para detectar patrones de error.

- Se valida acá, antes de marcar el ejercicio: un texto fuera de la lista o
  un valor que no es texto responde 400 `ENTRADA_INVALIDA` y el ejercicio
  queda sin responder. Si solo lo validara progreso-flask, su 400 llegaría
  al estudiante como el `aviso` de "el servicio de progreso no respondió".
- Ausente o `null`, la respuesta funciona como siempre.
- Con un acierto se ignora sin revisarlo, para que un cliente que lo manda
  de más no pierda la respuesta.
- Se guarda en `ejercicios.codigo_error` (RF-IA-02) cuando `acerto` es
  false, y NULL cuando es true, para calcular la curva de olvido al cerrar
  la sesión. Se reenvía a `POST .../respuestas/` de progreso-flask solo
  cuando existe; sin él, el cuerpo es el de siempre, `{"caracter", "acerto"}`.
- La respuesta no cambia de forma. Si progreso-flask no responde, el
  código se pierde junto con el resto del progreso de esa respuesta, y se
  devuelve el `aviso` de siempre.

Los 14 códigos (`dominio/codigos_error.py`) son los 12 `explicacion.codigo`
de evaluacion-flask (`TRAZO_*`, `PINYIN_*`, `SIGNIFICADO_*`) más
`TRAZO_AUTOCALIFICADO` ("Fallé" en un trazo) y `NO_SABE` ("No lo sé"). Un
servicio no importa código de otro, así que la lista es una copia:
`tests/test_codigos.py` la compara con `adaptadores/reglas.py` de
evaluacion-flask y con `dominio/codigos.py` de progreso-flask, leídos con
`ast`.

```json
{"ejercicio": {"id": 1, "caracter": "人", "tipo": "significado", "dificultad": 2, "es_refuerzo": false},
 "sesion_completada": false, "pendientes": 3,
 "proximo_repaso": "2026-10-24T20:32:45.555728+00:00", "tasa_acierto": 0.55}
```

`proximo_repaso` es una **estimación** del próximo repaso de ese carácter,
en el mismo formato que v1 (`+00:00`). Se calcula acá
(`dominio/repaso.py`) con los intervalos fijos de antes (1, 3, 7, 16, 35 o
90 días según la racha que devuelve progreso-flask, o 12 horas si falló).
Desde RF-IA-02 la fecha real la agenda progreso-flask con la curva de olvido
(SM-2) al cerrar la sesión, así que puede no coincidir con la que muestra
`GET /api/v2/progreso/<id>/repasos/` y la sección "Próximos repasos".

**Al cerrar la sesión (RF-IA-02).** Cuando la respuesta responde el último
ejercicio pendiente, después de registrarla en progreso-flask se llama a
`POST /api/v2/progreso/<id>/curva-olvido/` con:

- `sesion_id`;
- `cerrada_en`: la fecha de la última respuesta, con zona horaria;
- `respuestas`: una por ejercicio respondido de la sesión, en su orden, con
  `caracter`, `acerto` y `codigo_error` si existe.

Va después de registrar la respuesta porque ahí progreso-flask fija el
estado inicial de un carácter que ya tenía agenda. Es un POST: no se
reintenta. Si progreso-flask no responde o devuelve un error, queda una
advertencia en el log ("No se pudo aplicar la curva de olvido de la sesión
N"), la respuesta de responder no cambia y la sesión queda completada
igual. Esa sesión no se vuelve a enviar más tarde. progreso-flask es
idempotente por sesión: si dos respuestas cierran la misma sesión a la vez,
la curva se aplica una sola vez.

**Desempeño (RF-IA-05).** En cuanto la respuesta cierra la sesión, la
sesión ejecuta `calcular_desempeno()` (`calcularDesempeño()` del diagrama),
que procesa la duración y la fecha, y los resultados quedan registrados en
`sesiones` en el mismo commit que la última respuesta: `completada_en` (la
fecha de esa respuesta), `duracion_seg` y `aciertos`. La respuesta que
cierra trae además `desempeno` al final, con la misma forma que
`GET /api/v2/sesiones/<id>/desempeno/`. Las demás respuestas no cambian. No
depende de progreso-flask: con progreso caído el desempeño se registra
igual y la respuesta trae `desempeno` y después `aviso`.

`duracion_seg` y `aciertos` quedan para consultar la base directamente (un
reporte o un `SELECT`) sin recorrer los ejercicios. El servicio no los lee:
`calcular_desempeno()` cuenta los aciertos desde los ejercicios, porque ahí
también saca el desglose por tipo y porque así las sesiones cerradas antes
de RF-IA-05, que tienen esas columnas en NULL, dan el mismo resultado.

Si progreso-flask no responde, la respuesta igual queda guardada:

```json
{"ejercicio": {...}, "sesion_completada": false, "pendientes": 1,
 "proximo_repaso": null, "tasa_acierto": null,
 "aviso": "La respuesta quedó guardada en la sesión, pero no se pudo actualizar el progreso: el servicio de progreso no respondió."}
```

### `GET /api/v2/sesiones/<id>/desempeno/` (RF-IA-05)

Desempeño de una sesión terminada. `409 SESION_NO_COMPLETADA` si sigue en
curso y `404` si no existe.

```json
{"sesion_id": 12, "creada_en": "2026-11-10T15:00:00Z", "completada_en": "2026-11-10T15:08:30Z",
 "duracion_seg": 510, "duracion_estimada_min": 10, "dentro_del_tiempo": true,
 "segundos_por_ejercicio": 128, "total": 4, "aciertos": 3, "fallos": 1, "tasa_acierto": 0.75,
 "por_tipo": {"trazo": {"total": 2, "aciertos": 1}, "significado": {"total": 2, "aciertos": 2}}}
```

- `duracion_seg` va de `creada_en` (cuando empezó) a `completada_en` (la
  última respuesta), sin bajar de 0. `dentro_del_tiempo` es true si no pasó
  de `duracion_estimada_min`.
- `tasa_acierto` es la de esta sesión (aciertos sobre respondidos, con dos
  decimales), en la misma escala de 0 a 1 que la tasa global de
  progreso-flask, que es otra cosa: un promedio móvil de todas las
  respuestas.
- `por_tipo` solo trae los tipos que tiene la sesión.
- Las sesiones cerradas antes de RF-IA-05 no tienen `completada_en`
  guardado: se usa la fecha de su última respuesta, así que también tienen
  desempeño.

### `GET /api/v2/sesiones/desempeno/?usuario_id=<uuid>&limite=10` (RF-IA-05)

Las últimas `limite` (1 a 50, por defecto 10) sesiones terminadas del
usuario, de la más reciente a la más antigua, con los totales. Las sesiones
en curso no entran. Sin `usuario_id`, o con un UUID o un `limite`
inválidos, `400 ENTRADA_INVALIDA`.

```json
{"usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
 "resumen": {"sesiones": 2, "ejercicios": 14, "aciertos": 11, "tasa_acierto": 0.79, "duracion_seg": 960},
 "sesiones": [{"sesion_id": 13, ...}, {"sesion_id": 12, ...}]}
```

### Errores

Siempre `{"error": "<mensaje>", "codigo": "<CODIGO>"}`:

| Estado | `codigo`                  | Cuándo                                         |
|--------|---------------------------|------------------------------------------------|
| 400    | `ENTRADA_INVALIDA`        | Cuerpo inválido o fuera de rango, o `codigo_error` desconocido |
| 400    | `NIVEL_NO_PERMITIDO`      | El nivel pedido no está desbloqueado           |
| 400    | `SESION_INVALIDA`         | No alcanzan los ejercicios (mínimo 3, máximo 20) |
| 404    | `NO_ENCONTRADO`           | Sesión, ejercicio o ruta inexistente           |
| 405    | `METODO_NO_PERMITIDO`     | Método HTTP no soportado                       |
| 409    | `EJERCICIO_YA_RESPONDIDO` | El ejercicio ya fue respondido                 |
| 409    | `SESION_NO_COMPLETADA`    | Se pidió el desempeño de una sesión en curso   |
| 500    | `ERROR_INTERNO`           | Error inesperado (sin stack trace)             |

Diferencias con v1: los errores de validación eran el dict de DRF por campo
y ahora son un `error` con el campo en el mensaje; todos traen `codigo`; y
la respuesta puede traer `desempeno` cuando cierra la sesión y `aviso`
cuando progreso no respondió.

## Docker

```bash
docker build -t sesiones-flask services/sesiones-flask
```
