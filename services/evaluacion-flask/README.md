# evaluacion-flask

Microservicio Flask que decide si la respuesta a un ejercicio es correcta
(tarea T10 del Strangler Pattern). Reemplaza en `/api/v2/` a
`EvaluarEjercicioService` y `domain/evaluacion_logic.py` de
`services/agente-tutor` (app `tutor`). No importa código de otros servicios:
lo que necesita de catalogo-flask y trazos-flask lo pide por HTTP.

Sigue el estándar de [`docs/arquitectura/estandar-flask.md`](../../docs/arquitectura/estandar-flask.md)
y parte de la plantilla `services/flask-base`, con la misma estructura que
`services/sesiones-flask`.

## Evaluar no es responder

Son dos pasos distintos y quedan en servicios distintos:

| Paso      | Servicio          | Qué hace                                                    |
|-----------|-------------------|-------------------------------------------------------------|
| Evaluar   | evaluacion-flask  | Decide si la respuesta es correcta. No guarda nada.         |
| Responder | sesiones-flask    | Recibe `acerto`, marca el ejercicio y registra el progreso. |

Así el que corrige no conoce sesiones ni progreso, y el que registra no
conoce las reglas de cada tipo de ejercicio.

## Sin base de datos

El servicio no guarda estado: cada evaluación depende solo de la petición y
de los datos del catálogo, y el resultado lo registra sesiones-flask. Por
eso no tiene `db.py`, `modelos.py` ni `crear_base.py`, no usa
`DATABASE_URL` y `/health` no consulta ninguna base, igual que
`trazos-flask`. Tampoco depende de SQLAlchemy ni de psycopg2.

## Estructura

| Archivo                  | Responsabilidad                                                |
|--------------------------|----------------------------------------------------------------|
| `app.py`                 | Fábrica `create_app()`: config, errores, dependencias, rutas   |
| `config.py`              | Configuración desde variables de entorno                       |
| `dominio/evaluacion.py`  | Reglas de pinyin y significado (port de `evaluacion_logic.py`) |
| `dominio/excepciones.py` | Errores de negocio con su estado HTTP y su código              |
| `clientes.py`            | Cliente HTTP resiliente y clientes de catálogo y trazos        |
| `fabricas.py`            | Arma los clientes y les pasa el Accept-Language del usuario    |
| `i18n.py`, `mensajes.py`, `babel.cfg`, `translations/` | Mensajes en español e inglés (Flask-Babel) |
| `servicio.py`            | `EvaluacionService`: el caso de uso                            |
| `validacion.py`, `serializacion.py`, `rutas.py` | Entrada, JSON de salida y el endpoint   |

Equivalencias con v1 (`services/agente-tutor/tutor`):

| Django                                  | Flask                       |
|-----------------------------------------|-----------------------------|
| `domain/evaluacion_logic.py`            | `dominio/evaluacion.py`     |
| `services.py` (`EvaluarEjercicioService`) | `servicio.py`             |
| `infra/catalogo.py` (`obtener_detalle`) | `clientes.CatalogoRemoto`   |
| `infra/catalogo.py` (`comparar_trazo`, a contenido) | `clientes.TrazosRemoto` (a trazos-flask) |

## Reglas

- **pinyin**: pasa a minúsculas, colapsa espacios y quita tildes y tonos
  (NFD sin marcas combinantes) en la respuesta y en el pinyin del catálogo,
  y los compara. "xue", "xué" y "XUÉ" valen para `xué`. Como en v1, el tono
  no cuenta y la diéresis tampoco (`lu` vale para `lǜ`).
- **significado**: normaliza igual, cambia comas por espacios, ordena las
  palabras y compara con `SequenceMatcher`. Acierta si la similitud llega al
  umbral de la dificultad: 1 → 0.55, 2 → 0.65, 3 → 0.75, 4 → 0.85,
  5 → 0.92.
- **trazo**: busca en el detalle del catálogo el trazo con esa `secuencia`,
  manda su `mediana` y los puntos del usuario a trazos-flask y devuelve su
  veredicto. `acerto` es el `aprobado` de trazos-flask.

## Comunicación con otros servicios

| Servicio       | Variable       | Ruta que usa                         |
|----------------|----------------|--------------------------------------|
| catalogo-flask | `CATALOGO_URL` | `GET /api/v2/caracteres/<hanzi>/`    |
| trazos-flask   | `TRAZOS_URL`   | `POST /api/v2/trazos/validar/`       |

Las URL son la base del servicio, sin `/api/v2`. El cliente es el mismo de
sesiones-flask: timeout (`HTTP_TIMEOUT`), reintentos solo en GET
(`HTTP_REINTENTOS`) y errores tipados (`ServicioNoDisponible` para red,
timeout, 5xx o algo que no es JSON; `RespuestaRechazada` para un 4xx).

A diferencia de sesiones, acá no hay respuesta degradada. Si el catálogo o
trazos no responden, el servicio devuelve `503` con
`DEPENDENCIA_NO_DISPONIBLE` en vez de adivinar. v1 devolvía `False` (o
`"motivo": "error_servicio"` en trazos), y el usuario veía como error suyo
lo que era una caída. Con trazos caído, pinyin y significado siguen
funcionando porque solo usan el catálogo.

## Ejecutar

```bash
cd services/evaluacion-flask
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q

# Con catalogo-flask en 5081 y trazos-flask en 5082 (ver sus README).
# En macOS el puerto 5000 lo usa AirPlay.
CATALOGO_URL=http://127.0.0.1:5081 TRAZOS_URL=http://127.0.0.1:5082 \
  .venv/bin/gunicorn -w 2 -b 127.0.0.1:5087 "app:create_app()"
```

## Variables de entorno

| Variable           | Default                 | Uso                                   |
|--------------------|-------------------------|---------------------------------------|
| `SERVICE_NAME`     | `evaluacion-flask`      | Nombre que devuelve `/health`         |
| `HOST`, `PORT`     | `0.0.0.0`, `5000`       | Interfaz y puerto                     |
| `FLASK_DEBUG`      | `0`                     | `1` activa debug, solo en local       |
| `CATALOGO_URL`     | `http://localhost:5081` | URL base de catalogo-flask            |
| `TRAZOS_URL`       | `http://localhost:5082` | URL base de trazos-flask              |
| `HTTP_TIMEOUT`     | `3`                     | Segundos por petición a otro servicio |
| `HTTP_REINTENTOS`  | `2`                     | Reintentos de los GET                 |
| `GUNICORN_WORKERS` | `2`                     | Procesos de gunicorn (Docker)         |

## Idioma de los mensajes

Los textos de `error` salen en español o en inglés según la cabecera
`Accept-Language`; sin cabecera, o con otro idioma, en español. Las claves,
el `codigo` y el estado no cambian. Usa Flask-Babel igual que
`services/sesiones-flask`: el código marca los textos con `N_` y
`errores.py` los traduce al responder.

Además, el Accept-Language del usuario se reenvía a catalogo-flask y a
trazos-flask (`fabricas.idioma_del_usuario`). Así, cuando trazos rechaza los
puntos con un 400, su mensaje ya vuelve en el idioma del usuario y se
devuelve tal cual.

```bash
curl -s -X POST http://127.0.0.1:5087/api/v2/evaluacion/ -H "Accept-Language: en" \
  -H "Content-Type: application/json" -d '{"tipo": "audio", "caracter": "人", "respuesta": "x"}'
# {"error": "'tipo' must be one of: pinyin, significado, trazo", "codigo": "ENTRADA_INVALIDA"}
```

El `Dockerfile` compila los `.mo`; para correrlo en local,
`.venv/bin/pybabel compile -d translations`.

## Contrato

### `POST /api/v2/evaluacion/`

Cuerpo:

- `tipo`: `pinyin`, `significado` o `trazo`.
- `caracter`: el hanzi, por ejemplo `学`.
- `respuesta`: un texto para pinyin y significado; para trazo, un objeto
  con `secuencia` (desde 1, como en v1), `puntos`, `ancho` y `alto`, que
  son los que espera trazos-flask.
- `dificultad` (opcional, 1 a 5, por defecto 3): solo cambia el umbral del
  significado. En v1 salía del ejercicio guardado.

```bash
curl -s -X POST http://127.0.0.1:5087/api/v2/evaluacion/ \
  -H "Content-Type: application/json" \
  -d '{"tipo": "pinyin", "caracter": "人", "respuesta": "ren"}'
```

Pinyin y significado responden `200`:

```json
{"tipo": "pinyin", "caracter": "人", "acerto": true}
```

Trazo responde `200` con el veredicto de trazos-flask, en el orden de
`ResultadoComparacionSerializer` de v1:

```json
{"tipo": "trazo", "caracter": "人", "acerto": true, "secuencia": 1,
 "aprobado": true, "puntaje": 100, "motivo": "correcto", "invertido": false,
 "detalle": "Trazo correcto.", "puntos_lejanos": []}
```

### Errores

Siempre `{"error": "<mensaje>", "codigo": "<CODIGO>"}`:

| Estado | `codigo`                    | Cuándo                                                  |
|--------|-----------------------------|---------------------------------------------------------|
| 400    | `ENTRADA_INVALIDA`          | Cuerpo inválido, o puntos que trazos-flask rechaza      |
| 404    | `NO_ENCONTRADO`             | Carácter que no está en el catálogo, trazo inexistente o ruta desconocida |
| 405    | `METODO_NO_PERMITIDO`       | Método HTTP no soportado                                |
| 503    | `DEPENDENCIA_NO_DISPONIBLE` | Catálogo o trazos no respondieron                       |
| 500    | `ERROR_INTERNO`             | Error inesperado (sin stack trace)                      |

### Diferencias con v1

- v1 no tenía endpoint: `EvaluarEjercicioService` recibía el id de un
  ejercicio guardado. Acá llegan el carácter, el tipo y la dificultad.
- v1 devolvía un booleano para pinyin y significado; acá es un objeto con
  `acerto`.
- El trazo no trae `distancia_media` ni `razon_longitud`, porque
  trazos-flask no los devuelve.
- Una dependencia caída da `503` en vez de un resultado falso.

## Docker

```bash
docker build -t evaluacion-flask services/evaluacion-flask
docker run --rm -p 5087:5000 \
  -e CATALOGO_URL=http://host.docker.internal:5081 \
  -e TRAZOS_URL=http://host.docker.internal:5082 evaluacion-flask
```
