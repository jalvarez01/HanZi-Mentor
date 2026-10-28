# reportes-flask

Microservicio Flask de reportes asíncronos con Redis y Celery (tareas T18 y
T19 de la Entrega 2). La app Flask encola tareas y consulta su estado; el
worker de Celery las ejecuta. Los dos usan la misma imagen.

Sigue el estándar de [`docs/arquitectura/estandar-flask.md`](../../docs/arquitectura/estandar-flask.md).

## Sin base de datos

Los resultados de las tareas viven en Redis y caducan a las 24 h
(`result_expires=86400`); las notificaciones, a los 7 días. Por eso no
tiene `db.py` ni `crear_base.py` y no usa `DATABASE_URL`.

## API

| Método y ruta | Respuesta |
|---|---|
| `POST /api/v2/reportes/` con `{"usuario_id": "<uuid>"}` | `202 {"task_id", "estado": "pendiente"}` y `Location: /api/v2/reportes/<task_id>/` |
| `GET /api/v2/reportes/<task_id>/` | `200 {"task_id", "estado"}`, más `resultado` (listo) o `codigo` y `error` (error); `404` si no existe o caducó |
| `GET /api/v2/reportes/notificaciones/<usuario_id>/` | `200 {"usuario_id", "notificaciones": [...]}`, de la más nueva a la más vieja |

Estados:

| Celery | API |
|---|---|
| `PENDING`, `RECEIVED` | `pendiente` |
| `STARTED`, `RETRY` | `en_proceso` |
| `SUCCESS` | `listo` |
| `FAILURE`, `REVOKED` | `error` |

**task_id desconocido o caducado → 404.** Celery no guarda la lista de
tareas encoladas: para él, un id que nunca existió es `PENDING`, igual que
uno que espera en la cola. Por eso, al encolar, la API guarda la marca
`reporte:<task_id>` en Redis con la misma caducidad que los resultados
(24 h) y pasa ese mismo id a Celery (`send_task(..., task_id=...)`).

| Marca | Estado en Celery | Respuesta |
|---|---|---|
| No | `PENDING` | `404 NO_ENCONTRADO` |
| Sí | `PENDING` | `200 pendiente` (espera al worker) |
| Sí o no | `STARTED`, `RETRY`, `SUCCESS`, `FAILURE` | `200` con su estado |

El resultado se devuelve aunque falte la marca: con `volatile-lru`, Redis
puede expulsarla antes que el resultado. Si falla guardar la marca o
publicar la tarea, el POST responde 503 y no queda una marca huérfana.

Errores:

| Caso | Estado | `codigo` |
|---|---|---|
| `usuario_id` o `task_id` no es un UUID, o el cuerpo no es JSON | 400 | `ENTRADA_INVALIDA` |
| El `task_id` no existe o su reporte caducó (24 h) | 404 | `NO_ENCONTRADO` |
| Redis no responde (encolar, consultar o `/health`) | 503 | `COLA_NO_DISPONIBLE` |
| El reporte terminó en error porque progreso no respondió | 200, `estado: error` | `DEPENDENCIA_NO_DISPONIBLE` |
| El reporte terminó en error por otra causa | 200, `estado: error` | `ERROR_INTERNO` |

El texto de `error` sale en español o en inglés según `Accept-Language`.
El traceback de una tarea queda en Redis y nunca se devuelve.

### Reporte

Todos los campos salen de `GET /api/v2/progreso/<id>/` de progreso-flask,
salvo `generado_en` (ISO 8601 UTC):

```json
{
  "usuario_id": "…", "nivel_hsk": 1, "nivel_max_desbloqueado": 1,
  "tasa_acierto": 0.5, "total_dominados": 0, "total_por_reforzar": 0,
  "caracteres_dominados": [], "caracteres_debiles": [{"caracter": "学", "fallos": 2}],
  "proximo_repaso": null, "actualizado_en": null,
  "generado_en": "2026-10-26T21:00:00Z"
}
```

Un usuario sin actividad recibe los valores iniciales de progreso: su
reporte queda `listo`, no en error.

### Si progreso no responde

El `ClienteHttp` de la tarea va **sin reintentos HTTP** (`reintentos=0`);
reintenta solo Celery: `autoretry_for=DependenciaNoDisponible`,
`max_retries=3`, esperas de 1, 2 y 4 s, sin azar (`retry_jitter=False`).
Mientras espera, el estado es `en_proceso`.

Peor caso con `HTTP_TIMEOUT=3`: 4 intentos x 3 s + 7 s de espera = **19 s**
hasta `error`. Con el contenedor de progreso detenido, cada intento tarda
unos 4 s porque la resolución DNS del nombre no respeta el timeout: 4 x 4 s
+ 7 s = **23 s** (medido en Docker). Subir `HTTP_TIMEOUT` alarga ese
tiempo. Un 4xx de progreso no se reintenta.

### Notificaciones

La tarea `notificar_sesion_lista(usuario_id, sesion_id)` la publica
sesiones-flask por nombre. Deja una línea en el log del worker y guarda
`{"tipo": "sesion_lista", "sesion_id", "creada_en"}` en la lista Redis
`notificaciones:<usuario_id>` con `LPUSH` + `LTRIM 0 19` + `EXPIRE` de 7
días, en una transacción. No guarda resultado (`ignore_result`).

## Estructura

| Archivo                  | Responsabilidad                                                |
|--------------------------|----------------------------------------------------------------|
| `app.py`                 | Fábrica `create_app()`: config, errores, Redis, rutas y `/health` |
| `config.py`              | Configuración desde variables de entorno (Flask y worker)      |
| `tareas.py`              | `celery_app` y las tareas del worker                           |
| `fabricas.py`            | Cliente Redis, publicador Celery y dependencias de las tareas  |
| `clientes.py`            | `ClienteHttp` (igual que sesiones-flask) y `ProgresoRemoto`    |
| `notificaciones.py`      | Lista de notificaciones en Redis y su doble en memoria         |
| `dominio/reporte.py`     | Arma el JSON del reporte                                       |
| `dominio/excepciones.py` | `ErrorReporte(codigo, mensaje)` y `DependenciaNoDisponible`    |
| `servicio.py`            | Encolar, leer el estado y leer notificaciones                  |
| `validacion.py`, `rutas.py`, `errores.py` | Entrada, endpoints y errores JSON             |
| `i18n.py`, `mensajes.py`, `babel.cfg`, `translations/` | Mensajes en español e inglés (Flask-Babel) |

## Celery

Broker y backend: `REDIS_URL` (en Docker, `redis://redis:6379/0`).

| Ajuste                       | Valor  | Por qué                                         |
|------------------------------|--------|-------------------------------------------------|
| `task_serializer`, `result_serializer`, `accept_content` | `json` | El worker nunca deserializa pickle |
| `result_expires`             | 86400  | Los resultados caducan a las 24 h               |
| `task_track_started`         | True   | Distingue `en_proceso` de `pendiente`           |
| `task_soft_time_limit`       | 30     | Aviso a la tarea para que termine               |
| `task_time_limit`            | 40     | Límite duro: el worker corta el proceso hijo    |
| `worker_prefetch_multiplier` | 1      | Con `--concurrency=1`, una tarea por vez        |

La app Flask **encola con otra app Celery** (`fabricas.crear_publicador`),
por nombre de tarea, sin backend de resultados, sin reintentos de
publicación y con timeouts de 1 s. Con el backend de Redis, cada
publicación abriría una suscripción pub/sub que la app nunca usa y, con
Redis caído, tardaría unos 40 s en fallar; así responde 503 en 1 o 2 s. Los
resultados se leen con `tareas.celery_app.AsyncResult`, que es un GET.

En Redis (`docker-compose.yml`), `--maxmemory 64mb --maxmemory-policy
volatile-lru`: solo se expulsan claves con caducidad (resultados y
notificaciones). La cola no caduca y nunca se expulsa.

## Correrlo en local

Necesita un Redis en `localhost:6379` y progreso-flask en `localhost:5083`.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pybabel compile -d translations
.venv/bin/python app.py                                     # API en :5000
.venv/bin/celery -A tareas worker --loglevel=info --concurrency=1   # worker
```

En Windows, `--pool=solo` en el worker.

## Pruebas

No necesitan Redis, worker ni red: Celery corre en modo eager con un
backend en memoria (`cache+memory://`, que igual pasa los resultados por
JSON), progreso y las notificaciones son dobles en memoria, y el publicador
se inyecta en `create_app`.

```bash
.venv/bin/python -m pytest -q
```

## Ejemplo

Por el gateway:

```bash
curl -i -X POST http://localhost/api/v2/reportes/ \
  -H "Content-Type: application/json" \
  -d '{"usuario_id": "00000000-0000-0000-0000-000000000000"}'
# HTTP/1.1 202 Accepted
# Location: /api/v2/reportes/<task_id>/
# {"task_id":"<task_id>","estado":"pendiente"}

curl http://localhost/api/v2/reportes/<task_id>/
# {"task_id":"<task_id>","estado":"listo","resultado":{...}}

curl http://localhost/api/v2/reportes/notificaciones/00000000-0000-0000-0000-000000000000/
# {"usuario_id":"…","notificaciones":[]}
```
