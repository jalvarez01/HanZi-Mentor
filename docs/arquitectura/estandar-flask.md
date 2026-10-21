# Estándar de microservicios Flask

Reglas comunes para todos los servicios Flask que se extraen del monolito
Django con el Strangler Pattern. La implementación de referencia es
`services/trazos-flask` y la plantilla para servicios nuevos es
`services/flask-base`.

Servicios que deben cumplirlo:

| Servicio           | Tarea | Base de datos propia | Estado        |
|--------------------|-------|----------------------|---------------|
| `trazos-flask`     | Taller 02 | No (sin estado)      | Cumple        |
| `catalogo-flask`   | T13   | Sí                   | Por crear     |
| `evaluacion-flask` | T10   | Según diseño         | Por crear     |
| `progreso-flask`   | T11   | Sí                   | Por crear     |
| `sesiones-flask`   | T12   | Sí                   | Por crear     |

## Checklist

Un servicio cumple el estándar cuando se puede marcar todo esto:

- [ ] **Dockerfile propio** en la carpeta del servicio: `python:3.11-slim`,
      usuario sin privilegios, gunicorn con `app:create_app()` y `HEALTHCHECK`
      contra `/health`. Solo copia su propia carpeta.
- [ ] **`GET /health`** responde `200 {"estado": "ok", "servicio": "<nombre>"}`.
      Si usa base de datos, la consulta y responde `503` con
      `"codigo": "DB_NO_DISPONIBLE"` cuando no está disponible.
- [ ] **Errores en JSON**: toda respuesta de error tiene la forma
      `{"error": "<mensaje>", "codigo": "<CODIGO>"}`. Hay manejadores
      globales para 400, 404, 405, 500 y cualquier excepción. Nunca se
      devuelve HTML ni el stack trace.
- [ ] **Reglas de negocio** incumplidas se lanzan como `ErrorDominio`
      (400 por defecto, o el estado que corresponda, por ejemplo 409).
- [ ] **pytest** con `app.test_client()`: como mínimo `/health`, 404, 405,
      500 y un caso de `ErrorDominio`, más las pruebas de cada endpoint.
      Todas pasan con `pytest -q`.
- [ ] **Sin Django**: ningún `import django` ni `from django...`, ni
      dependencias de los servicios Django. La lógica que se trae del
      monolito se copia y se adapta (por ejemplo, `django.utils.timezone`
      pasa a `datetime.now(timezone.utc)`).
- [ ] **Base de datos propia** si el servicio guarda estado: SQLAlchemy 2.x
      con `DATABASE_URL`. SQLite local por defecto, PostgreSQL en Docker. No
      lee tablas de otro servicio; si necesita datos ajenos, los pide por HTTP.
- [ ] **Configuración por entorno**: `SERVICE_NAME`, `HOST`, `PORT`,
      `FLASK_DEBUG`, `DATABASE_URL` y las propias del servicio se leen en
      `config.py`. Nada de puertos, URLs ni claves en el código. Hay un
      `.env.example` con todas.
- [ ] **Versiones fijadas** en `requirements.txt`.
- [ ] **README.md** con cómo correrlo, probarlo y un `curl` de ejemplo.

## Estructura de carpetas

```
services/<nombre>-flask/
  app.py            create_app(config_extra): config, db, errores, blueprints, /health
  config.py         desde_entorno(): lee las variables de entorno
  db.py             Base, iniciar_db, obtener_sesion, db_disponible (si usa DB)
  errores.py        manejadores JSON y ErrorDominio
  rutas.py          blueprint: valida la forma de la entrada, llama al servicio, responde
  validacion.py     validación de la entrada (opcional si es simple)
  servicio.py       casos de uso: orquesta dominio, repositorios y clientes HTTP
  dominio/          reglas de negocio puras, sin Flask ni SQLAlchemy
  modelos.py        modelos SQLAlchemy (si usa DB)
  tests/            pytest
  Dockerfile
  .dockerignore
  .env.example
  requirements.txt
  pytest.ini
  README.md
```

Las capas solo dependen hacia adentro: `rutas` usa `servicio`, `servicio`
usa `dominio` y `modelos`. El controlador no tiene lógica de negocio.

## Cómo crear un servicio nuevo

1. Copiar la plantilla:
   ```bash
   cp -r services/flask-base services/<nombre>-flask
   ```
2. Cambiar `SERVICE_NAME` en `Dockerfile` y `.env.example`.
3. Agregar modelos, rutas, servicio y dominio siguiendo la estructura de
   arriba. Importar los modelos en `app.py` antes de `iniciar_db(app)`.
4. Si el servicio no guarda estado, definir `DATABASE_URL=` (vacío) y borrar
   `db.py`, como hace `trazos-flask`.
5. Mantener `tests/test_base.py` y agregar las pruebas propias.
6. Exponer las rutas bajo `/api/v2/<modulo>/` para que Nginx las enrute sin
   chocar con `/api/v1/` (Django).

## Integración con Docker y Nginx

En `docker-compose.yml`, cada servicio:

- usa el nombre `flask_<modulo>` (por ejemplo `flask_catalogo`);
- no publica puertos en el host, solo `expose: ["5000"]`;
- recibe `SERVICE_NAME` y `DATABASE_URL` por `environment`;
- si usa PostgreSQL, tiene su propia base (no comparte la de `contenido`) y
  `depends_on` con `condition: service_healthy`;
- tiene `restart: unless-stopped`.

En `infra/nginx/nginx.conf`, cada servicio tiene su `upstream` y un
`location /api/v2/<modulo>/` con `proxy_pass` sin URI, para que Flask reciba
la ruta completa.
