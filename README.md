# HanZi Mentor

Plataforma para aprender mandarín: enseña el orden correcto de los trazos de
cada carácter (hanzi), arma sesiones de práctica según los errores de cada
estudiante y aplica repaso espaciado.

**Proyecto académico** de SI3001 Arquitectura de Software, Universidad EAFIT.

---

## Arquitectura

El proyecto empezó como un monolito Django y se está migrando a
microservicios Flask con el Strangler Pattern. Las dos versiones conviven
detrás de Nginx, que decide por el prefijo de la URL quién atiende cada
petición:

- `/api/v1/...` va a los servicios Django originales (`contenido` y
  `agente-tutor`), que quedan como respaldo.
- `/api/v2/...` va a los microservicios Flask, que son los que usa el
  frontend.
- Todo lo demás va al frontend (una PWA en React servida por su propio Nginx).

```
                       navegador / celular
                               |
                               v
                   +-----------------------+
                   |  nginx  (puerto 80)   |   único puerto publicado
                   +-----------------------+
          /api/v1/ |       /api/v2/        |  /
     +-------------+           |           +-------------+
     v                         v                         v
 v1 (Django)            v2 (Flask)                  frontend
 - contenido            - flask_catalogo            (React + Vite)
 - agente_tutor         - flask_progreso
                        - flask_sesiones
                        - flask_evaluacion
                        - flask_trazos
                        - flask_ejemplos ----> Tatoeba (API externa)
     |                         |
     v                         v
 +-----------------------------------------------------+
 | PostgreSQL `db`: una base por servicio              |
 |   contenido, db_catalogo, db_progreso, db_sesiones  |
 +-----------------------------------------------------+
 agente_tutor usa su propio SQLite (volumen agente_tutor_db).
 flask_trazos, flask_evaluacion y flask_ejemplos no guardan estado.
```

Los servicios v2 no comparten código ni leen bases ajenas: lo que necesitan
de otro servicio lo piden por HTTP (por ejemplo, sesiones le pide caracteres
a catálogo y registra las respuestas en progreso; evaluación busca la mediana
del trazo en catálogo y la compara en trazos).

```
HanZi-Mentor/
├── services/
│   ├── contenido/          # Django v1: caracteres, trazos y lecciones
│   ├── agente-tutor/       # Django v1: sesiones, respuestas, progreso y tutor LangGraph
│   ├── usuarios/           # Django: cuentas (todavía no está en docker-compose.yml)
│   ├── catalogo-flask/     # v2: caracteres, lecciones y resumen público
│   ├── progreso-flask/     # v2: progreso y repaso espaciado
│   ├── sesiones-flask/     # v2: sesiones adaptativas y respuestas
│   ├── evaluacion-flask/   # v2: decide si una respuesta es correcta
│   ├── trazos-flask/       # v2: compara un trazo con su mediana
│   ├── ejemplos-flask/     # v2: oraciones de ejemplo de Tatoeba (patrón Adapter)
│   └── flask-base/         # plantilla de los servicios Flask
├── frontend/               # React + Vite (PWA mobile-first)
├── infra/nginx/nginx.conf  # el gateway
├── docker-compose.yml
└── docs/arquitectura/      # estándar Flask y coexistencia v1/v2
```

El estándar que cumplen los servicios Flask está en
[`docs/arquitectura/estandar-flask.md`](docs/arquitectura/estandar-flask.md).

---

## Servicios y rutas

Sacado de `infra/nginx/nginx.conf` y `docker-compose.yml`:

| Servicio (compose)   | Versión | Prefijo en nginx                             | Módulo |
|----------------------|---------|----------------------------------------------|--------|
| `contenido`          | v1      | `/api/v1/` (se reescribe a `/api/`)          | `services/contenido` |
| `agente_tutor`       | v1      | `/api/v1/tutor/` (se reescribe a `/api/`)    | `services/agente-tutor` |
| `flask_catalogo`     | v2      | `/api/v2/caracteres/`, `/api/v2/lecciones/`, `/api/v2/publico/` | `services/catalogo-flask` |
| `flask_progreso`     | v2      | `/api/v2/progreso/`                          | `services/progreso-flask` |
| `flask_sesiones`     | v2      | `/api/v2/sesiones/`, `/api/v2/ejercicios/`   | `services/sesiones-flask` |
| `flask_evaluacion`   | v2      | `/api/v2/evaluacion/`                        | `services/evaluacion-flask` |
| `flask_trazos`       | v2      | `/api/v2/trazos/`                            | `services/trazos-flask` |
| `flask_ejemplos`     | v2      | `/api/v2/ejemplos/`                          | `services/ejemplos-flask` |
| `frontend`           | -       | `/`                                          | `frontend` |
| `db`                 | -       | (sin ruta, solo red interna)                 | PostgreSQL 16 |

Cualquier otra ruta bajo `/api/` responde 404 en JSON desde el gateway. Cada
servicio tiene su README con el contrato completo de sus endpoints.

---

## Requisitos

- Docker y Docker Compose. Se probó con Docker 29.4 y Docker Compose v5.1
  (Docker Desktop). Cualquier versión reciente con `docker compose` debería
  andar.
- Conexión a internet en el primer arranque: si no está el dataset de
  caracteres, `contenido` y `flask_catalogo` lo descargan solos (unos 33 MB).
- El puerto 80 libre. **Solo nginx publica un puerto en el host**; los demás
  servicios y la base quedan dentro de la red de Docker.

Para correr los tests sin Docker hace falta además Python 3.12 (Django 4.2
no soporta versiones más nuevas). Para desarrollar el frontend fuera de
Docker, Node.js 22, la misma versión de la imagen del frontend.

---

## Levantar el proyecto en local

```bash
# 1. Clonar
git clone https://github.com/jalvarez01/HanZi-Mentor.git
cd HanZi-Mentor

# 2. Variables de entorno (opcional: sin .env se usan los valores por defecto)
cp .env.example .env      # Windows: copy .env.example .env

# 3. Construir y levantar todo
docker compose up -d --build

# 4. Ver el estado
docker compose ps
```

Todos los servicios que tienen healthcheck tienen que quedar `(healthy)`;
`contenido` y `nginx` no tienen healthcheck y aparecen solo como `Up`. La
primera vez puede tardar un poco más, porque se descarga y se carga el
dataset de caracteres (696 de HSK 1 a 6).

Después abrir el frontend en **<http://localhost>**.

Para seguir las peticiones (cada línea dice a qué servicio fue):

```bash
docker compose logs -f nginx
```

Para detener todo: `docker compose down` (con `-v` también borra las
bases). Si el puerto 80 está ocupado, cambiar `GATEWAY_PORT` en `.env`.

---

## Probar la API por nginx

Respuestas reales de un stack recién levantado, recortadas.

**1. Una ruta v1 (Django, respaldo del Strangler)**

```bash
curl "http://localhost/api/v1/caracteres/?nivel=1&limite=3"
```

```json
{"caracteres":[{"hanzi":"一","pinyin":"yī","definicion":"one; a, an; alone","nivel_hsk":1},
 {"hanzi":"七","pinyin":"qī","definicion":"seven","nivel_hsk":1},
 {"hanzi":"三","pinyin":"sān","definicion":"three","nivel_hsk":1}]}
```

**2. Crear una sesión de práctica (v2)**

```bash
curl -X POST http://localhost/api/v2/sesiones/ -H "Content-Type: application/json" \
  -d '{"usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "nivel_hsk": 1}'
```

```json
{"id":1,"usuario_id":"3fa85f64-5717-4562-b3fc-2c963f66afa6","nivel_hsk":1,"dificultad":2,
 "estado":"activa","duracion_estimada_min":10,"creada_en":"2026-10-27T20:27:14.945736Z",
 "ejercicios":[{"id":1,"caracter":"一","tipo":"significado","dificultad":2,"es_refuerzo":false}, ...]}
```

**3. Responder un ejercicio** (el `id` sale de la respuesta anterior)

```bash
curl -X POST http://localhost/api/v2/ejercicios/1/responder/ \
  -H "Content-Type: application/json" -d '{"acerto": true}'
```

```json
{"ejercicio":{"id":1,"caracter":"一","tipo":"significado","dificultad":2,"es_refuerzo":false},
 "sesion_completada":false,"pendientes":3,"proximo_repaso":"2026-10-28T20:27:14.977948+00:00","tasa_acierto":0.55}
```

La respuesta queda registrada en progreso:
`curl http://localhost/api/v2/progreso/3fa85f64-5717-4562-b3fc-2c963f66afa6/`
ya devuelve `"tasa_acierto":0.55` y `"aciertos_consecutivos":{"一":1}`.

**4. Evaluar un trazo** (el primer trazo de 人, dibujado en un lienzo de 300 x 300)

```bash
curl -X POST http://localhost/api/v2/evaluacion/ -H "Content-Type: application/json" \
  -d '{"tipo": "trazo", "caracter": "人", "respuesta": {"secuencia": 1,
       "puntos": [[142,48],[149,58],[150,65],[139,102],[120,142],[96,175],[79,192],[42,223],[21,236]],
       "ancho": 300, "alto": 300}}'
```

```json
{"tipo":"trazo","caracter":"人","acerto":true,"secuencia":1,"aprobado":true,"puntaje":100,
 "motivo":"correcto","invertido":false,"detalle":"Trazo correcto.","puntos_lejanos":[]}
```

**5. Resumen público para el equipo aliado, en inglés**

```bash
curl "http://localhost/api/v2/publico/resumen/?lang=en"
```

```json
{"sistema":"HanziMentor","caracteres_totales":696,
 "por_nivel_hsk":{"1":83,"2":71,"3":92,"4":117,"5":183,"6":150},
 "caracter_del_dia":{"hanzi":"甲","pinyin":"jiǎ","definicion":"armor, shell; fingernails; 1st heavenly stem","nivel_hsk":5},
 "generado_en":"2026-10-27T20:27:15Z"}
```

El carácter del día cambia cada día (UTC).

---

## Idioma de los mensajes

Los mensajes de error de todos los servicios, y los que arma el propio
gateway (502, 503, 504 y el 404 de `/api/`), salen en español o en inglés
según la cabecera `Accept-Language`. Sin cabecera, o con otro idioma, en
español. Solo cambia el texto: las claves, el `codigo` y el estado HTTP son
los mismos en los dos idiomas. El frontend manda el idioma elegido en su
selector.

```bash
curl "http://localhost/api/v2/caracteres/?limite=0" -H "Accept-Language: en"
# {"error":"The limit must be an integer between 1 and 100","codigo":"ENTRADA_INVALIDA"}
```

El resumen público acepta además `lang=es|en`, que manda sobre
`Accept-Language` en sus errores, porque el aliado lo llama desde su
backend:

```bash
curl "http://localhost/api/v2/publico/resumen/?lang=en&nivel=9"
# {"error":"The field 'nivel' must be an integer between 1 and 6","codigo":"ENTRADA_INVALIDA"}
```

---

## Tests

Cada servicio se prueba por separado con su propio entorno virtual, desde su
carpeta (en Windows, `.venv\Scripts\pytest` y `venv\Scripts\python`).

Servicios Flask (`catalogo-flask`, `progreso-flask`, `sesiones-flask`,
`evaluacion-flask`, `trazos-flask`, `ejemplos-flask` y `flask-base`):

```bash
cd services/catalogo-flask
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
```

Servicios Django (`contenido` y `agente-tutor`):

```bash
cd services/contenido
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python manage.py test
```

Totales de hoy:

| Servicio | Tests |
|----------|------:|
| catalogo-flask | 102 |
| progreso-flask | 70 |
| sesiones-flask | 93 |
| evaluacion-flask | 89 |
| trazos-flask | 21 |
| ejemplos-flask | 46 (+1 que se salta: la prueba en vivo contra Tatoeba) |
| flask-base | 19 |
| contenido | 39 |
| agente-tutor | 53 |
| **Total** | **532** |

La prueba en vivo de ejemplos se activa con `TATOEBA_EN_VIVO=1`. Los tests
de contrato de los servicios Flask leen los serializers de Django del mismo
repo, así que hay que correrlos con el repo completo (dentro de una imagen
Docker se saltan).

---

## Volver a v1 en un módulo

v1 sigue publicado en el gateway como respaldo, así que se puede volver a
Django sin tocar los servicios: o se revierte el cambio del frontend, o se
apunta la location v2 de nginx al servicio Django. Los pasos, la tabla de
cada módulo y sus límites están en
[`docs/arquitectura/strangler-v1-v2.md`](docs/arquitectura/strangler-v1-v2.md).

---

## Desarrollo del frontend sin Docker

Con el stack levantado, el servidor de Vite reenvía `/api` al gateway
(`VITE_GATEWAY_URL`, por defecto `http://localhost:80`):

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
npm run dev -- --host  # para abrirlo desde el celular en la misma red
```

Las variables del frontend están en `frontend/.env.example`; vacías usan el
mismo origen.

---

## Variables de entorno

`.env.example` documenta todas las variables. El archivo `.env` está en
`.gitignore` y nunca se sube.

**`ALLOWED_HOSTS`** merece nota aparte: en local se deja `*`, pero **en
producción hay que poner el dominio real** (por ejemplo
`ALLOWED_HOSTS=hanzimentor.app,www.hanzimentor.app`) y nunca `*`: con el
valor abierto, Django no valida la cabecera `Host` y queda expuesto a ataques
de host header injection.

---

## Datos de caracteres

Los caracteres se arman con dos fuentes externas:

| Fuente | Qué aporta | Repo |
|---|---|---|
| **Make Me a Hanzi** | El carácter (pinyin, definición, radical, descomposición) y sus **trazos** (orden, `path_svg` y `mediana`), que son los que se usan para validar la escritura. | [skishore/makemeahanzi](https://github.com/skishore/makemeahanzi) |
| **Complete HSK Vocabulary** | Solo el nivel HSK (1 a 6), volcado en `hsk.py`. | [drkameleon/complete-hsk-vocabulary](https://github.com/drkameleon/complete-hsk-vocabulary) |

En Docker no hay que hacer nada: si `services/contenido/data_hanzi` no
existe, `contenido` y `flask_catalogo` descargan el dataset y cargan los
caracteres de HSK 1 a 6 cuando su base está vacía. Para no descargarlo en
cada instancia nueva se puede clonar una vez (la carpeta está en
`.gitignore`):

```bash
git clone --depth 1 https://github.com/skishore/makemeahanzi services/contenido/data_hanzi
```

Los comandos para cargarlo a mano están en el README de
[`catalogo-flask`](services/catalogo-flask/README.md) (`cargar.py`) y, para
v1, `python manage.py cargar_hanzi` y `clasificar_hsk` en `contenido`.

---

## Instalar como app (PWA)

El frontend es una PWA: se instala en el celular sin pasar por las tiendas.

- **Android (Chrome):** el navegador ofrece "Instalar aplicación".
- **iOS (Safari):** botón Compartir y "Agregar a pantalla de inicio".
- **Escritorio (Chrome/Edge):** ícono de instalación en la barra de direcciones.

---

## Despliegue en AWS

Se completa con el despliegue en EC2.

---

## Stack

**Backend:** Django 4.2 + Django REST Framework (v1); Flask 3.1, SQLAlchemy 2 y Flask-Babel (v2)
**Base de datos:** PostgreSQL 16 (una base por servicio)
**Gateway:** Nginx 1.27
**Frontend:** React 19, Vite, React Router, PWA (vite-plugin-pwa), i18next
**Tutor:** LangGraph (motor `REAL` de agente-tutor, solo en v1)
**Infraestructura:** Docker y Docker Compose

---

## Equipo

- Emmanuel Castaño
- Juan José Álvarez
- Santiago Meneses

Profesor: Nicolás Ramírez Vélez
Universidad EAFIT, Escuela de Ciencias Aplicadas e Ingeniería
Medellín, Antioquia
