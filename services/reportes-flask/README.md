# reportes-flask

Microservicio Flask de reportes asíncronos con Redis y Celery (tareas T18 y
T19 de la Entrega 2). La app Flask encola tareas y consulta su estado; el
worker de Celery las ejecuta. Los dos usan la misma imagen.

Sigue el estándar de [`docs/arquitectura/estandar-flask.md`](../../docs/arquitectura/estandar-flask.md).

## Sin base de datos

Los resultados de las tareas viven en Redis y caducan a las 24 h
(`result_expires=86400`). Por eso no tiene `db.py` ni `crear_base.py` y no
usa `DATABASE_URL`.

## Estructura

| Archivo                  | Responsabilidad                                                |
|--------------------------|----------------------------------------------------------------|
| `app.py`                 | Fábrica `create_app()`: config, errores, Redis y `/health`     |
| `config.py`              | Configuración desde variables de entorno (Flask y worker)      |
| `tareas.py`              | `celery_app` y las tareas del worker (por ahora `ping`)        |
| `errores.py`             | Manejadores JSON y `ErrorDominio`                              |
| `i18n.py`, `mensajes.py`, `babel.cfg`, `translations/` | Mensajes en español e inglés (Flask-Babel) |

## Celery

Broker y backend: `REDIS_URL` (en Docker, `redis://redis:6379/0`).

| Ajuste                       | Valor  | Por qué                                         |
|------------------------------|--------|-------------------------------------------------|
| `task_serializer`, `result_serializer`, `accept_content` | `json` | El worker nunca deserializa pickle |
| `result_expires`             | 86400  | Los resultados caducan a las 24 h               |
| `task_track_started`         | True   | Distingue "en proceso" de "pendiente"           |
| `task_soft_time_limit`       | 30     | Ninguna tarea queda colgada                     |
| `worker_prefetch_multiplier` | 1      | Con `--concurrency=1`, una tarea por vez        |

En Redis (`docker-compose.yml`), `--maxmemory 64mb --maxmemory-policy
volatile-lru`: solo se expulsan claves con caducidad (resultados). La cola
no caduca y nunca se expulsa.

## Correrlo en local

Necesita un Redis en `localhost:6379`.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pybabel compile -d translations
.venv/bin/python app.py                                     # API en :5000
.venv/bin/celery -A tareas worker --loglevel=info --concurrency=1   # worker
```

En Windows, `--pool=solo` en el worker.

## Pruebas

No necesitan Redis ni worker: el cliente de Redis se inyecta en
`create_app` y las tareas se llaman directamente o en modo eager.

```bash
.venv/bin/python -m pytest -q
```

## Ejemplo

Dentro de Docker (el servicio no publica puertos):

```bash
docker compose exec flask_reportes python -c "from tareas import ping; print(ping.delay().get(timeout=10))"
# pong
docker compose exec flask_reportes python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:5000/health').read().decode())"
# {"estado":"ok","servicio":"reportes-flask"}
```
