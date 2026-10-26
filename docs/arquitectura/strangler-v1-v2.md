# Coexistencia de v1 y v2 (Strangler Pattern)

Estado de la migración del monolito Django a los microservicios Flask (T17).
Todo pasa por el gateway (`infra/nginx/nginx.conf`), que decide por el
prefijo de la URL quién atiende cada petición:

- `/api/v1/...` va a los servicios Django: `contenido` (con el rewrite de
  `/api/v1/` a `/api/`) y `agente_tutor` (de `/api/v1/tutor/` a `/api/`).
- `/api/v2/...` va a los servicios Flask, que reciben la ruta completa.

Las dos versiones responden el mismo JSON (mismas claves y mismo orden). Lo
comprueban los `tests/test_contrato.py` de cada servicio Flask, que leen los
serializers de v1.

## Estado por módulo

| Módulo | v1 (Django) | v2 (Flask) | Quién lo consume | Estado |
|--------|-------------|------------|------------------|--------|
| Trazos | `POST /api/v1/caracteres/<hanzi>/trazos/<n>/validar/` (contenido) | `POST /api/v2/trazos/validar/` (flask_trazos) | flask_evaluacion (v2), como servicio interno; agente-tutor sigue validando contra contenido (v1) | Migrado. v1 queda para agente-tutor |
| Caracteres | `GET /api/v1/caracteres/`, `/api/v1/caracteres/<hanzi>/` (contenido) | `GET /api/v2/caracteres/`, `/api/v2/caracteres/<hanzi>/` (flask_catalogo) | Frontend, agente-tutor y flask_sesiones (v2) | Migrado. v1 de respaldo |
| Lecciones | `POST /api/v1/lecciones/generar/`, `GET /api/v1/lecciones/<id>/` (contenido) | Las mismas rutas bajo `/api/v2/` (flask_catalogo) | Frontend (v2) | Migrado. v1 de respaldo |
| Progreso | `GET /api/v1/tutor/progreso/<uuid>/` (agente_tutor) | `GET /api/v2/progreso/<uuid>/` (flask_progreso) | Frontend y flask_sesiones (v2) | Migrado. v1 de respaldo |
| Sesiones | `POST /api/v1/tutor/sesiones/`, `GET /api/v1/tutor/sesiones/<id>/` (agente_tutor) | `POST /api/v2/sesiones/`, `GET /api/v2/sesiones/<id>/` (flask_sesiones) | Frontend (v2) | Migrado. v1 de respaldo |
| Ejercicios | `POST /api/v1/tutor/ejercicios/<id>/responder/` (agente_tutor) | `POST /api/v2/ejercicios/<id>/responder/` (flask_sesiones) | Frontend (v2) | Migrado. v1 de respaldo |
| Evaluación | Sin ruta pública (`EvaluarEjercicioService` dentro de agente_tutor) | `POST /api/v2/evaluacion/` (flask_evaluacion) | Frontend (Trazos, v2) | Migrado. v1 sin endpoint |
| Ejemplos | No existe | `GET /api/v2/ejemplos/<hanzi>/` (flask_ejemplos, Tatoeba) | Todavía ningún cliente | Nuevo en v2 |

Lo que sigue en Django:

- **usuarios** (`services/usuarios`): no está en `docker-compose.yml` ni
  detrás del gateway. El frontend genera un UUID local por usuario.
- **Tutor con LangGraph** (`TUTOR_ENGINE=REAL` en agente-tutor): depende del
  agente y de sus credenciales, así que no se portó. flask_sesiones solo
  acepta `TUTOR_ENGINE=MOCK`.
- La validación de trazos que usa agente-tutor internamente
  (`CONTENIDO_URL`), que sigue yendo a contenido v1.

## Bases de datos

Cada servicio tiene su base dentro del PostgreSQL compartido `db`:
`contenido` (Django), `db_catalogo`, `db_progreso` y `db_sesiones`.
agente-tutor sigue con su SQLite en el volumen `agente_tutor_db`.

v1 y v2 **no comparten datos**. Las sesiones y el progreso que se registran
por v2 no se ven en v1, y al revés. Por eso v1 es solo un respaldo para
emergencias y no una segunda fuente de verdad.

## Cómo volver a v1

v1 sigue publicado en el gateway, así que volver no requiere tocar los
servicios. Hay dos formas, según hasta dónde se quiera volver.

**1. Solo el frontend.** Las funciones de `frontend/src/services/api.js`
eligen la versión en la ruta, y las variables `VITE_*_URL` solo cambian el
origen (vacías, mismo origen). Para volver hay que revertir el commit que
pasó el cliente a v2 y reconstruir el frontend:

| Funciones | Base v2 | Base v1 |
|-----------|---------|---------|
| `crearSesion`, `obtenerSesion`, `responderEjercicio` | `${VITE_SESIONES_URL}/api/v2` | `${VITE_TUTOR_URL}/api/v1/tutor` |
| `obtenerProgreso` | `${VITE_PROGRESO_URL}/api/v2` | `${VITE_TUTOR_URL}/api/v1/tutor` |
| `listarCaracteres`, `obtenerCaracter`, `generarLeccion`, `obtenerLeccion` | `${VITE_CATALOGO_URL}/api/v2` | `${VITE_CONTENIDO_URL}/api/v1` |
| `evaluar` (Trazos) | `${VITE_EVALUACION_URL}/api/v2` | `${VITE_CONTENIDO_URL}/api/v1/caracteres/<hanzi>/trazos/<n>/validar/` |

La página de Trazos ya no llama a trazos-flask: le manda a evaluación el
carácter, la secuencia y los puntos, y evaluación busca la mediana en el
catálogo y compara con trazos-flask. Volver a v1 en Trazos es volver a
llamar a contenido con el hanzi y la secuencia en la ruta.

**2. En el gateway, sin reconstruir el frontend.** Como el JSON es el mismo,
basta con apuntar la location v2 al servicio Django con el mismo rewrite que
usa v1 y recargar Nginx (`docker compose exec nginx nginx -s reload`). Por
ejemplo, para sesiones:

```nginx
        location /api/v2/sesiones/ {
            set $destino http://agente_tutor:8003;
            rewrite ^/api/v2/(.*)$ /api/$1 break;
            proxy_pass $destino;
        }
```

Sirve igual para `/api/v2/ejercicios/` y `/api/v2/progreso/` (agente_tutor)
y para `/api/v2/caracteres/` y `/api/v2/lecciones/` (`contenido:8002`). No
sirve para trazos ni para evaluación: las rutas de trazos en v1 y v2 son
distintas, y la evaluación no tiene endpoint en v1. Las
respuestas de error de v1 vuelven a ser el dict por campo de DRF en vez de
`{"error", "codigo"}`.

Dentro de los servicios:

- agente-tutor con `CATALOGO=LOCAL` deja de pedirle caracteres a
  flask_catalogo y usa su lista propia.
- flask_sesiones no tiene vuelta a v1: si catálogo o progreso no responden,
  sigue en modo degradado (lista local, progreso inicial y `aviso` en la
  respuesta). Ver la sección "Comunicación entre servicios" de
  [`estandar-flask.md`](estandar-flask.md).

## Cuándo se retira v1

v1 se mantiene solo como respaldo mientras v2 se estabiliza. Se puede quitar
del gateway (y apagar `contenido` y las rutas de `tutor` y `progreso` de
agente-tutor) cuando:

- agente-tutor valide los trazos contra flask_trazos y deje de usar
  `CONTENIDO_URL`;
- el tutor con LangGraph tenga un reemplazo o pase a consumir v2;
- el healthcheck de agente_tutor deje de consultar `/api/progreso/`.
