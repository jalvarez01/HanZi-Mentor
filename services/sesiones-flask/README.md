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
| `modelos.py`           | `SesionEstudio` y `Ejercicio`                                    |
| `dominio/builder.py`   | `SesionEstudioBuilder` con todas las validaciones de v1          |
| `dominio/sesion.py`    | Ciclo de vida: pendientes y cierre de la sesión                  |
| `dominio/repaso.py`    | Intervalos del repaso, para informar `proximo_repaso`            |
| `dominio/excepciones.py` | Errores de negocio con su estado HTTP y su código              |
| `clientes.py`          | Cliente HTTP resiliente y clientes de catálogo y progreso        |
| `motores.py`           | `MotorTutor` y `MotorTutorMock` (dificultad y caracteres nuevos) |
| `notificadores.py`     | `Notificador` y el adaptador de consola                          |
| `fabricas.py`          | Elige motor, notificador y clientes según la configuración       |
| `repositorio.py`       | Acceso a la base; guarda sesión y ejercicios en una transacción  |
| `servicio.py`          | `SesionEstudioService` y `ResponderEjercicioService`             |
| `validacion.py`, `serializacion.py`, `rutas.py` | Entrada, JSON igual a v1 y los tres endpoints |
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

## Motor y notificador

- `TUTOR_ENGINE`: solo `MOCK`. El motor con LangGraph sigue en agente-tutor
  porque depende del agente y de sus credenciales. Cualquier otro valor hace
  fallar el arranque con un mensaje claro.
- `NOTIFICADOR`: solo `CONSOLE`, que deja una línea en el log. El de email
  usaba el backend de correo de Django.

## Comunicación con otros servicios (base de T16)

| Servicio      | Variable       | Rutas que usa                                                    |
|---------------|----------------|------------------------------------------------------------------|
| catalogo-flask| `CATALOGO_URL` | `GET /api/v2/caracteres/?nivel=&excluir=&limite=`                |
| progreso-flask| `PROGRESO_URL` | `GET /api/v2/progreso/<id>/`, `GET .../refuerzos/?limite=3`, `POST .../respuestas/` |

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
| Refuerzos caídos              | La sesión se arma sin refuerzos                               |
| POST de respuesta caído       | La respuesta queda guardada en la sesión y se devuelve `aviso` |

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
| `NOTIFICADOR`      | `CONSOLE`               | Notificador (solo CONSOLE)                   |
| `GUNICORN_WORKERS` | `2`                     | Procesos de gunicorn (Docker)                |

## Base de datos en Docker

Mismo esquema que catalogo-flask y progreso-flask: un solo PostgreSQL (`db`)
con una base por servicio. La de este es `db_sesiones`:

`DATABASE_URL=postgresql+psycopg2://hanzimentor:hanzimentor@db:5432/db_sesiones`

Al arrancar, `crear_base.py` crea la base si no existe (si existe, solo lo
informa), se crean las tablas una sola vez y arranca gunicorn. Si PostgreSQL
no responde, el servicio arranca igual y `/health` responde 503.

## Contrato

Las respuestas tienen las mismas claves, en el mismo orden, que los
serializers de agente-tutor (`tests/test_contrato.py` lo comprueba).

### `POST /api/v2/sesiones/`

Cuerpo: `usuario_id` (UUID, o un entero como acepta DRF), `nivel_hsk` (1 a
6) y `duracion_min` (5 a 60, por defecto 10). Responde `201`. Los refuerzos
(los caracteres con más fallos, tipo `trazo`) van primero.

```json
{"id": 2, "usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "nivel_hsk": 1, "dificultad": 2,
 "estado": "activa", "duracion_estimada_min": 10, "creada_en": "2026-10-23T20:32:45.598104Z",
 "ejercicios": [
   {"id": 5, "caracter": "你", "tipo": "trazo", "dificultad": 2, "es_refuerzo": true},
   {"id": 7, "caracter": "大", "tipo": "significado", "dificultad": 2, "es_refuerzo": false}]}
```

Nivel bloqueado: `400 {"error": "HSK3 aún no está desbloqueado (máximo actual: HSK1).", "codigo": "NIVEL_NO_PERMITIDO"}`,
con el mismo mensaje que v1.

### `GET /api/v2/sesiones/<id>/`

Misma forma que la respuesta de creación.

### `POST /api/v2/ejercicios/<id>/responder/`

Cuerpo: `{"acerto": true}` (acepta los mismos valores que `BooleanField` de
DRF). Marca el ejercicio, cierra la sesión si era el último y registra la
respuesta en progreso-flask.

```json
{"ejercicio": {"id": 1, "caracter": "人", "tipo": "significado", "dificultad": 2, "es_refuerzo": false},
 "sesion_completada": false, "pendientes": 3,
 "proximo_repaso": "2026-10-24T20:32:45.555728+00:00", "tasa_acierto": 0.55}
```

`proximo_repaso` es la fecha del próximo repaso de ese carácter, en el mismo
formato que v1 (`+00:00`). progreso-flask no expone la agenda por carácter,
así que se calcula acá con los mismos intervalos y la racha que devuelve
progreso-flask; puede diferir en milisegundos de la que guardó progreso.

Si progreso-flask no responde, la respuesta igual queda guardada:

```json
{"ejercicio": {...}, "sesion_completada": false, "pendientes": 1,
 "proximo_repaso": null, "tasa_acierto": null,
 "aviso": "La respuesta quedó guardada en la sesión, pero no se pudo actualizar el progreso: el servicio de progreso no respondió."}
```

### Errores

Siempre `{"error": "<mensaje>", "codigo": "<CODIGO>"}`:

| Estado | `codigo`                  | Cuándo                                         |
|--------|---------------------------|------------------------------------------------|
| 400    | `ENTRADA_INVALIDA`        | Cuerpo inválido o fuera de rango               |
| 400    | `NIVEL_NO_PERMITIDO`      | El nivel pedido no está desbloqueado           |
| 400    | `SESION_INVALIDA`         | No alcanzan los ejercicios (mínimo 3, máximo 20) |
| 404    | `NO_ENCONTRADO`           | Sesión, ejercicio o ruta inexistente           |
| 405    | `METODO_NO_PERMITIDO`     | Método HTTP no soportado                       |
| 409    | `EJERCICIO_YA_RESPONDIDO` | El ejercicio ya fue respondido                 |
| 500    | `ERROR_INTERNO`           | Error inesperado (sin stack trace)             |

Diferencias con v1: los errores de validación eran el dict de DRF por campo
y ahora son un `error` con el campo en el mensaje; todos traen `codigo`; y
la respuesta puede traer `aviso` cuando progreso no respondió.

## Docker

```bash
docker build -t sesiones-flask services/sesiones-flask
```
