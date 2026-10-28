# Entrega 2 — Migración a Microservicios, Integración y Resiliencia

Documentación de la Entrega 2 de HanZi Mentor: el paso del monolito Django a
un ecosistema híbrido de microservicios Flask detrás de Nginx, desplegado en
AWS Academy, con integración con un equipo aliado y una API de terceros,
tareas asíncronas e internacionalización.

> **Estado de esta página (27/10/2026):** por ahora incluye las correcciones
> de la Entrega 1 y la justificación del bono de excelencia, que se adelantó
> para revisarla antes del Parcial 02. Las secciones de arquitectura y
> diagramas, servicios (aliado y API de terceros), despliegue en AWS, i18n y
> usabilidad, tareas asíncronas y evidencias se agregan antes de la entrega
> del 12 de noviembre.

---

## 1. Correcciones de la Entrega 1

La sustentación de la Entrega 1 no generó correcciones: el profesor no
notificó observaciones sobre el código, la arquitectura ni la documentación
entregada. Por eso no hay ajustes pendientes, y la condición de la rúbrica
(implementar el 100 % de las correcciones de la Entrega 1 para que esta
entrega sea revisada) se cumple sin cambios.

| Observación del profesor | Estado | Evidencia |
|--------------------------|--------|-----------|
| Ninguna en la sustentación de la Entrega 1 | No aplica | — |

Si el profesor notifica alguna corrección después, se agregará a esta tabla
con el commit o el Pull Request que la resuelve.

---

## 2. Bono de excelencia: más del 70 % migrado a microservicios

El enunciado exime del Parcial 02 a los equipos que migren más del 70 % de
sus servicios y lógica de negocio a microservicios funcionales e
independientes. HanZi Mentor migró a Flask **todos los endpoints de negocio
del monolito**: el 100 % de los módulos existentes y el 83 % si se cuentan
también los módulos nuevos de esta entrega.

### Cómo se mide

Cada módulo pesa tanto como **endpoints de negocio** tenía en el monolito
(inventario del 23/10/2026). Un módulo cuenta como migrado solo si cumple
todo esto:

- Servicio Flask propio, con su Dockerfile.
- Base de datos propia si guarda estado (un PostgreSQL compartido con una
  base por servicio: `db_catalogo`, `db_progreso`, `db_sesiones`). Si no
  guarda estado, sin base.
- `GET /health`, errores en JSON y pruebas con pytest.
- Ningún `import django`: la lógica se copió y se adaptó, no se importa.
- Ruta `/api/v2/...` publicada en Nginx.
- Al menos un consumidor real: el frontend u otro servicio.

### Módulos

| Módulo | Origen (Django) | Microservicio | Rutas v2 | Peso | Estado | Evidencia | Lo consume |
|--------|-----------------|---------------|----------|:----:|--------|-----------|------------|
| Validación de trazos | `contenido` | `trazos-flask` | `POST /api/v2/trazos/validar/` | 1 | Migrado | PR #20 (`3eef230`) | `evaluacion-flask` |
| Catálogo de caracteres | `contenido` | `catalogo-flask` | `GET /api/v2/caracteres/`, `GET /api/v2/caracteres/<hanzi>/` | 2 | Migrado | PR #25 (`debe6e7`), integrado en PR #30 (`dd82852`) | Frontend, `sesiones-flask`, `evaluacion-flask`, `agente-tutor` |
| Lecciones | `contenido` | `catalogo-flask` | `POST /api/v2/lecciones/generar/`, `GET /api/v2/lecciones/<id>/` | 2 | Migrado | PR #25 (`debe6e7`), integrado en PR #30 (`dd82852`) | Frontend |
| Progreso y repaso espaciado | `agente-tutor` | `progreso-flask` | `GET /api/v2/progreso/<usuario>/` | 1 | Migrado | PR #28 (`f393bb6`), en el gateway con PR #31 (`4851679`) | Frontend, `sesiones-flask` |
| Sesiones adaptativas y respuestas | `agente-tutor` | `sesiones-flask` | `POST /api/v2/sesiones/`, `GET /api/v2/sesiones/<id>/`, `POST /api/v2/ejercicios/<id>/responder/` | 2 | Migrado | PR #29 (`771eb01`), en el gateway con PR #31 (`4851679`) | Frontend |
| Evaluación de ejercicios | `agente-tutor` | `evaluacion-flask` | `POST /api/v2/evaluacion/` | 1 | Migrado | PR #32 (`6ac6664`), consumo en PR #35 (`728db41`) | Frontend |
| Agente tutor (LangGraph) | `agente-tutor` | — | — | 0 | Permanece en Django | — | — |
| Usuarios | `usuarios` | — | — | 0 | Permanece en Django | — | — |
| Ejemplos de oraciones (API de terceros) | Nuevo | `ejemplos-flask` | `GET /api/v2/ejemplos/<hanzi>/` | 1 | Migrado | PR #27 (`f9ebcdc`), integrado en PR #30 (`dd82852`), consumo en PR #37 (`2d58af2`) | Frontend (pantalla de Trazos) |
| Servicio para el equipo aliado | Nuevo | `catalogo-flask` | `GET /api/v2/publico/resumen/` | 1 | En progreso | PR #38 | Pendiente: equipo aliado |
| Reportes y notificaciones | Nuevo | `flask_reportes` + worker de Celery | `/api/v2/reportes/` | 1 | Pendiente | — | Frontend |

Los dos módulos con peso 0 no tienen endpoints de negocio propios:

- **Agente tutor**: es el motor que arma las sesiones. Su versión
  determinista (`MOCK`) se portó dentro de `sesiones-flask` (`motores.py`);
  la versión con LangGraph, que llama a un modelo de IA, sigue en
  `agente-tutor` y solo la usa la ruta v1.
- **Usuarios**: el servicio solo expone el panel `admin/` de Django.

### Resultado

| Cálculo | Peso migrado | Peso total | Porcentaje |
|---------|:------------:|:----------:|:----------:|
| Solo los módulos que existían en el monolito | 9 | 9 | **100 %** |
| Todos los módulos, incluidos los nuevos de esta entrega | 10 | 12 | **83 %** |

Los dos cálculos superan la meta del 70 %. Cuando el equipo aliado consuma
el servicio público (T14), el segundo sube a 92 %.

### Coexistencia con el monolito (Strangler Pattern)

El frontend y los servicios ya usan solo las rutas `/api/v2/`. Las rutas
`/api/v1/` de `contenido` y `agente-tutor` siguen publicadas en Nginx como
respaldo, como pide el patrón: si un servicio nuevo falla, v1 todavía
responde. Se retirarán cuando se apaguen esos servicios Django.

### Verificación

Verificado el 26/10/2026 sobre `development` (commit `728db41`), en local
con Docker. El consumo de `ejemplos-flask` desde la pantalla de Trazos
(PR #37) se verificó el mismo día en el navegador, en español y en inglés.
Falta repetirlo en la instancia de AWS.

- `docker compose up -d --build` levanta los 11 contenedores y todos los
  que tienen healthcheck quedan `healthy`.
- Pruebas de cada servicio con pytest: 21 (trazos), 71 (catálogo),
  67 (progreso), 89 (sesiones), 85 (evaluación) y 42 (ejemplos); 375 en
  total, todas pasan.
- Ninguno de los seis servicios importa Django.
- Cada ruta v2 responde a través de Nginx, en un flujo real:

| Petición por Nginx | Respuesta |
|--------------------|-----------|
| `GET /api/v2/caracteres/?nivel=1&limite=3` | 200, 一 七 三 |
| `GET /api/v2/caracteres/人/` | 200, con sus 2 trazos |
| `POST /api/v2/lecciones/generar/` y `GET /api/v2/lecciones/<id>/` | 201 y 200, 3 ejercicios |
| `POST /api/v2/trazos/validar/` | 200, con el veredicto del trazo |
| `GET /api/v2/ejemplos/学/` | 200, oraciones de Tatoeba |
| `POST /api/v2/sesiones/` y `GET /api/v2/sesiones/<id>/` | 201 y 200, sesión activa con 4 ejercicios |
| `POST /api/v2/ejercicios/<id>/responder/` | 200; `progreso-flask` actualiza la tasa de acierto (0.5 → 0.55) |
| `POST /api/v2/evaluacion/` (pinyin) | 200, `acerto: true` |
| `GET /api/v2/caracteres/?limite=abc` con `Accept-Language: en` | 400 en JSON, mensaje en inglés |
| `GET /api/v1/caracteres/` | 200, el respaldo v1 sigue activo |

Para repetirlo:

```bash
docker compose up -d --build
docker compose ps
curl "http://localhost/api/v2/caracteres/?nivel=1&limite=3"
curl -X POST http://localhost/api/v2/sesiones/ -H "Content-Type: application/json" \
  -d '{"usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "nivel_hsk": 1, "duracion_min": 10}'
docker compose logs nginx   # cada línea muestra a qué servicio fue la petición
```
