# Estándar de microservicios Flask

Reglas comunes para todos los servicios Flask que se extraen del monolito
Django con el Strangler Pattern. La implementación de referencia es
`services/trazos-flask` y la plantilla para servicios nuevos es
`services/flask-base`.

Servicios que deben cumplirlo:

| Servicio           | Tarea | Base de datos propia | Estado        |
|--------------------|-------|----------------------|---------------|
| `trazos-flask`     | Taller 02 | No (sin estado)      | Cumple        |
| `catalogo-flask`   | T13   | Sí                   | Cumple        |
| `evaluacion-flask` | T10   | Según diseño         | Por crear     |
| `progreso-flask`   | T11   | Sí                   | Cumple        |
| `sesiones-flask`   | T12   | Sí                   | Cumple        |

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
- [ ] **i18n con Flask-Babel**: los textos para el usuario (`error`,
      `detalle`, `aviso`) salen en español o en inglés según
      `Accept-Language`, en español por defecto. Están marcados con `N_` o
      `gettext`, tienen su `.po` en `translations/es` y `translations/en`, y
      el `Dockerfile` los compila con `pybabel compile`. Las claves, el
      `codigo` y el estado nunca se traducen.
- [ ] **Versiones fijadas** en `requirements.txt`.
- [ ] **README.md** con cómo correrlo, probarlo y un `curl` de ejemplo.

## Estructura de carpetas

```
services/<nombre>-flask/
  app.py            create_app(config_extra): config, db, errores, blueprints, /health
  config.py         desde_entorno(): lee las variables de entorno
  i18n.py           Flask-Babel: idioma según Accept-Language y traducir()
  mensajes.py       N_(): marca textos traducibles sin importar Flask
  babel.cfg         qué archivos revisa pybabel extract
  translations/     es/ y en/ con su messages.po (los .mo no se suben)
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

## Mensajes en español e inglés

El idioma lo elige la cabecera `Accept-Language` (`es` o `en`; sin cabecera,
o con otro idioma, `es`). Es la misma regla que usan los servicios Django
con `LocaleMiddleware`. Solo se traduce el texto: las claves del JSON, el
`codigo` y el estado son los mismos en los dos idiomas, así el cliente no
depende del idioma para decidir qué hacer.

El texto se escribe en español en el código y se traduce al responder:

- En el **dominio**, que no importa Flask, se marca con `N_()` de
  `mensajes.py` (no traduce, solo lo marca para pybabel). Si lleva datos,
  van como marcadores con nombre y aparte, no con f-strings, para que cada
  idioma pueda ordenar la frase:
  ```python
  raise NivelNoPermitidoError(
      N_("HSK%(nivel)s aún no está desbloqueado (máximo actual: HSK%(maximo)s)."),
      nivel=3, maximo=1,
  )
  raise ErrorDominio(N_("El límite debe ser como máximo %(maximo)s"),
                     "ENTRADA_INVALIDA", params={"maximo": 50})
  ```
- En el **borde HTTP** (`errores.py`, la serialización), `i18n.traducir()`
  lo pasa al idioma de la petición. `str(error)` sigue dando el texto en
  español, así las pruebas y los logs no cambian.

Para agregar un mensaje nuevo:

1. Escribirlo en español con `N_()` (o `gettext()` si ya se está en una
   ruta) y marcadores `%(nombre)s` para los datos.
2. Actualizar los catálogos desde la carpeta del servicio:
   ```bash
   .venv/bin/pybabel extract -F babel.cfg --ignore-dirs='.* ._ tests' -o messages.pot .
   .venv/bin/pybabel update -i messages.pot -d translations
   ```
3. Completar el `msgstr` en `translations/en/LC_MESSAGES/messages.po` (en
   `es` queda vacío, porque el `msgid` ya está en español).
4. Agregar una prueba con `headers={"Accept-Language": "en"}`. Las pruebas
   compilan los `.mo` solas (`tests/conftest.py`); para correr el servicio
   en local, `.venv/bin/pybabel compile -d translations`.

## Comunicación entre servicios

Un servicio nunca importa código de otro ni lee su base: pide lo que
necesita por HTTP a la URL base del otro servicio (sin `/api/v2`), que llega
por variable de entorno, por ejemplo `CATALOGO_URL=http://flask_catalogo:5000`.

La implementación de referencia es `services/sesiones-flask/clientes.py`
(base de T16):

- **Timeout** en cada petición (`HTTP_TIMEOUT`, 3 s por defecto).
- **Reintentos acotados** con una espera corta y creciente, solo en GET
  (`HTTP_REINTENTOS`, 2 por defecto). No se reintenta un 4xx ni un POST.
- **Respuesta degradada**: si el otro servicio no responde, el cliente
  devuelve un valor de respaldo (una lista local, valores por defecto) o
  la ruta agrega un campo `aviso`, en vez de responder 500. Nunca se
  reenvía al cliente una página HTML de error.

## Integración con Docker y Nginx

En `docker-compose.yml`, cada servicio:

- usa el nombre `flask_<modulo>` (por ejemplo `flask_catalogo`);
- no publica puertos en el host, solo `expose: ["5000"]`;
- recibe `SERVICE_NAME` y `DATABASE_URL` por `environment`;
- si usa PostgreSQL, tiene su propia base `db_<modulo>` dentro del
  PostgreSQL compartido `db` (no comparte la de `contenido`), que crea su
  `crear_base.py` en el arranque, y `depends_on: db` con
  `condition: service_healthy`;
- tiene `restart: unless-stopped`.

En `infra/nginx/nginx.conf`, cada servicio tiene su `upstream` y un
`location /api/v2/<modulo>/` con `proxy_pass` sin URI, para que Flask reciba
la ruta completa.
