# Coexistencia de v1 y v2 (Strangler Pattern)

Estado de la migración del monolito Django a los microservicios Flask (T17).
Todo pasa por el gateway (`infra/nginx/nginx.conf`), que decide por el
prefijo de la URL quién atiende cada petición:

- `/api/v1/...` va a los servicios Django: `contenido` (con el rewrite de
  `/api/v1/` a `/api/`) y `agente_tutor` (de `/api/v1/tutor/` a `/api/`).
- `/api/v2/...` va a los servicios Flask, que reciben la ruta completa.

Las dos versiones responden el mismo JSON (mismas claves y mismo orden). Lo
comprueban los `tests/test_contrato.py` de cada servicio Flask, que leen los
serializers de v1. Las excepciones deliberadas están en "Diferencias
deliberadas con v1", más abajo.

## Estado por módulo

| Módulo | v1 (Django) | v2 (Flask) | Quién lo consume | Estado |
|--------|-------------|------------|------------------|--------|
| Trazos | `POST /api/v1/caracteres/<hanzi>/trazos/<n>/validar/` (contenido) | `POST /api/v2/trazos/validar/` (flask_trazos) | flask_evaluacion (v2), como servicio interno; agente-tutor sigue validando contra contenido (v1) | Migrado. v1 queda para agente-tutor |
| Caracteres | `GET /api/v1/caracteres/`, `/api/v1/caracteres/<hanzi>/` (contenido) | `GET /api/v2/caracteres/`, `/api/v2/caracteres/<hanzi>/` (flask_catalogo) | Frontend, agente-tutor y flask_sesiones (v2) | Migrado. v1 de respaldo |
| Lecciones | `POST /api/v1/lecciones/generar/`, `GET /api/v1/lecciones/<id>/` (contenido) | Las mismas rutas bajo `/api/v2/` (flask_catalogo) | Frontend (v2) | Migrado. v1 de respaldo |
| Progreso | `GET /api/v1/tutor/progreso/<uuid>/` (agente_tutor) | `GET /api/v2/progreso/<uuid>/` (flask_progreso) | Frontend y flask_sesiones (v2) | Migrado. v1 de respaldo |
| Patrones de error | No existe | `POST /api/v2/progreso/<uuid>/errores/`, `GET /api/v2/progreso/<uuid>/patrones/` (flask_progreso) | Frontend (Trazos, Práctica y Progreso) | Nuevo en v2 (RF-IA-01) |
| Curva de olvido | No existe (agenda con intervalos fijos en cada respuesta) | `POST /api/v2/progreso/<uuid>/curva-olvido/`, `GET /api/v2/progreso/<uuid>/repasos/` (flask_progreso) | flask_sesiones (al cerrar la sesión y al armarla) y frontend (Progreso) | Nuevo en v2, cambia el repaso de v1 (RF-IA-02) |
| Sesiones | `POST /api/v1/tutor/sesiones/`, `GET /api/v1/tutor/sesiones/<id>/` (agente_tutor) | `POST /api/v2/sesiones/`, `GET /api/v2/sesiones/<id>/` (flask_sesiones) | Frontend (v2) | Migrado. v1 de respaldo |
| Ejercicios | `POST /api/v1/tutor/ejercicios/<id>/responder/` (agente_tutor) | `POST /api/v2/ejercicios/<id>/responder/` (flask_sesiones) | Frontend (v2) | Migrado. v1 de respaldo |
| Evaluación | Sin ruta pública (`EvaluarEjercicioService` dentro de agente_tutor) | `POST /api/v2/evaluacion/` (flask_evaluacion) | Frontend (Trazos y Práctica, v2) | Migrado, con diferencias deliberadas (ver abajo). v1 sin endpoint |
| Ejemplos | No existe | `GET /api/v2/ejemplos/<hanzi>/` (flask_ejemplos, Tatoeba) | Todavía ningún cliente | Nuevo en v2 |
| Reportes | No existe | `POST /api/v2/reportes/`, `GET /api/v2/reportes/<task_id>/`, `GET /api/v2/reportes/notificaciones/<uuid>/` (flask_reportes + worker) | Todavía ningún cliente (frontend en T20) | Nuevo en v2 |

### Diferencias deliberadas con v1

evaluacion-flask ya no es un port idéntico de `evaluacion_logic.py` (RF-IA-04):

- **Significado**: acepta un sentido suelto de la definición ("good" para
  好, que en v1 daba 0.17 contra la definición completa y fallaba). Un
  sentido de 1 a 3 letras ("an", "one") solo acierta con coincidencia
  exacta. Los umbrales por dificultad son los de v1.
- **Respuesta**: agrega dos campos opcionales al final, `explicacion` (si la
  respuesta falla) y `nota` (tono de un pinyin correcto, o dónde mejorar un
  trazo aprobado como "aceptable"). Las claves de v1
  no cambian de nombre ni de orden.
- trazos-flask agrega `razon_longitud` a su respuesta, que v1 (contenido)
  ya devolvía; evaluación la usa para explicar el error, sin exponerla.

Detalle en el README de `services/evaluacion-flask`.

progreso-flask agrega, sin equivalente en v1 (RF-IA-01):

- **Registro de errores por tipo**: `POST .../respuestas/` acepta un
  `codigo_error` opcional (el `explicacion.codigo` de evaluación,
  `NO_SABE` o `TRAZO_AUTOCALIFICADO`), que flask_sesiones reenvía desde
  `POST /api/v2/ejercicios/<id>/responder/`. Se guarda en dos columnas
  nuevas de `progresos`, `errores_por_codigo` e `historial_errores`, que
  agrega una migración idempotente. Las respuestas no cambian de forma.
- **`POST /api/v2/progreso/<uuid>/errores/`**: la página Trazos anota el
  tipo de error de un trazo fallado. Solo alimenta los patrones; no toca
  racha, dominados, tasa ni repaso.
- **`GET /api/v2/progreso/<uuid>/patrones/`**: los patrones de error del
  estudiante en los últimos 14 días, con título y consejo traducidos.

Las tres rutas quedan bajo `location /api/v2/progreso/` del gateway, sin
cambios en Nginx. Volver a v1 en el gateway (más abajo) las deja sin
destino: agente_tutor no las tiene. Trazos y el aviso de fin de sesión
siguen sin mostrar nada; la sección "Tus patrones de error" de Progreso
muestra su estado de error con "Reintentar", y el resto de la página
funciona. v1 ignora `codigo_error` en `responder`.

RF-IA-02 (curva de olvido) cambia el repaso espaciado que venía de v1:

| Tema | v1 (y v2 antes de RF-IA-02) | v2 desde RF-IA-02 |
|------|-----------------------------|-------------------|
| Algoritmo | Intervalos fijos según la racha: 1, 3, 7, 16, 35 o 90 días; 12 horas tras un fallo | SM-2 por carácter con factor de facilidad (2.5 al empezar, mínimo 1.3): 1 día, 6 días y después `round(intervalo x facilidad)`; 12 horas tras un fallo |
| Calidad de la respuesta | Solo acierto o fallo | De 0 a 4 según el `codigo_error`: acierto 4, fallo cercano 2, fallo 1, `NO_SABE` 0 |
| Cuándo se agenda | En cada respuesta (`ResponderEjercicioService`) | Una vez por carácter al cerrar la sesión, con su peor respuesta: flask_sesiones llama a `POST .../curva-olvido/`, idempotente por sesión (tabla `sesiones_aplicadas`) |
| `proximo_repaso` | Solo cambiaba si la fecha nueva era anterior: quedaba una fecha vieja que nunca se corregía | Siempre la fecha más cercana de la agenda, calculada al leer |
| Repasos vencidos | No se usaban: un carácter dominado no volvía a una sesión | `GET .../repasos/`; flask_sesiones pone hasta 4 vencidos primero, y la sección "Próximos repasos" de Progreso los muestra |

- Las respuestas mantienen la forma de v1. `proximo_repaso` de `responder`
  sigue siendo la estimación con intervalos fijos; la fecha real es la de
  `repasos/`.
- `db_progreso` suma la columna `curva_olvido` y la tabla
  `sesiones_aplicadas`; `db_sesiones` suma `ejercicios.codigo_error`. Las
  dos migraciones son idempotentes y no reescriben filas. Los caracteres
  agendados con el algoritmo anterior conservan su fecha y toman su estado
  SM-2 de la racha la primera vez que se vuelven a responder.
- Volver a v1 en el gateway deja `repasos/` sin destino: la sección
  "Próximos repasos" muestra su estado de error con "Reintentar". flask_sesiones
  llama a flask_progreso por su URL interna (`PROGRESO_URL`), no por el
  gateway, así que la curva se sigue aplicando en v2; v1 no la conoce y
  sigue agendando con intervalos fijos sobre su propia base.

Lo que sigue en Django:

- **usuarios** (`services/usuarios`): no está en `docker-compose.yml` ni
  detrás del gateway. El frontend genera un UUID local por usuario.
- **Tutor con LangGraph** (`TUTOR_ENGINE=REAL` en agente-tutor): depende del
  agente y de sus credenciales, así que no se portó. flask_sesiones solo
  acepta `TUTOR_ENGINE=MOCK`.
- La validación de trazos que usa agente-tutor internamente
  (`CONTENIDO_URL`), que sigue yendo a contenido v1.

## Tareas asíncronas

Los reportes y las notificaciones no existen en v1: son nuevos en v2 y no
tienen vuelta atrás. `flask_reportes` encola en `redis` y el servicio
`worker` (Celery, misma imagen) ejecuta:

- `generar_reporte_progreso(usuario_id)`: pide el progreso a flask_progreso
  por HTTP y guarda el resumen en Redis 24 h. El cliente consulta
  `GET /api/v2/reportes/<task_id>/` hasta `listo` o `error`; un `task_id`
  que no existe o ya caducó responde `404 NO_ENCONTRADO`.
- `notificar_sesion_lista(usuario_id, sesion_id)`: la publica
  flask_sesiones al crear una sesión; queda en el log del worker y en la
  lista `notificaciones:<usuario_id>` (las últimas 20, 7 días).

Si `redis` o `worker` se caen, nada de v1 ni del resto de v2 deja de
funcionar: encolar un reporte responde 503 y la sesión se crea igual.

## Bases de datos

Cada servicio tiene su base dentro del PostgreSQL compartido `db`:
`contenido` (Django), `db_catalogo`, `db_progreso` y `db_sesiones`.
agente-tutor sigue con su SQLite en el volumen `agente_tutor_db`.
`flask_reportes` no tiene base: sus resultados viven en `redis`, sin
persistencia.

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
