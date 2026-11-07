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
| `dominio/puertos.py`     | Puerto `ExplicadorErrores` (RF-IA-04)                          |
| `dominio/explicacion.py` | `ErrorEvaluado`, `Explicacion` y `Nota`                        |
| `dominio/pinyin.py`, `dominio/notas.py` | Tono, inicial y final de una sílaba; notas de tono y de mejora |
| `dominio/geometria.py`   | Zonas, direcciones y tramos de un trazo a partir de su mediana |
| `adaptadores/`           | Adaptador `reglas` y la fábrica que elige el explicador        |
| `clientes.py`            | Cliente HTTP resiliente y clientes de catálogo y trazos        |
| `fabricas.py`            | Arma los clientes (con el Accept-Language del usuario) y el explicador |
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
  (NFD sin marcas combinantes) en la respuesta y en cada lectura del
  catálogo, y los compara. "xue", "xué" y "XUÉ" valen para `xué`. Las
  lecturas salen de `lecturas` del detalle; si un catálogo anterior no la
  manda, vale solo `pinyin`. Acierta con cualquiera: 长 vale como "chang" o
  como "zhang", y 得 como "de" o "dei". Como en v1, el tono
  no cuenta y la diéresis tampoco (`lu` vale para `lǜ`).
- **significado**: normaliza igual, cambia comas por espacios, ordena las
  palabras y compara con `SequenceMatcher`. Acierta si la similitud llega al
  umbral de la dificultad (1: 0.55, 2: 0.65, 3: 0.75, 4: 0.85,
  5: 0.92). Se compara con la definición completa y con el sentido al que
  más se parece la respuesta (la definición se separa en sentidos por `;` y
  por `,`), así "good" acierta para 好.
  - Sentidos cortos: si el sentido más parecido tiene de 1 a 3 letras ("a",
    "an", "one"), solo acierta la coincidencia exacta, tras normalizar
    (minúsculas, sin puntuación ni espacios de más). Así "man" y "on" no
    aciertan para 一 y "one" sí. Una definición que es un solo sentido
    corto ("big") también exige coincidencia exacta.
  - Limitación: las definiciones del catálogo (Make Me a Hanzi) están en
    inglés y no hay traducciones; una respuesta en español no acierta.
- **trazo**: busca en el detalle del catálogo el trazo con esa `secuencia`,
  manda su `mediana` y los puntos del usuario a trazos-flask y devuelve su
  veredicto. `acerto` es el `aprobado` de trazos-flask.

## Feedback pedagógico (RF-IA-04)

Cuando la respuesta falla, el servicio explica por qué y qué hacer en el
siguiente intento. Cuando un pinyin acierta, agrega una nota con su tono; cuando
un trazo se aprueba como "aceptable" con un tramo desviado, una nota que dice
dónde mejorar.

### Puerto y adaptador

- `dominio/puertos.py` define el puerto `ExplicadorErrores` con un solo
  método: `explicar_error(tipo, error) -> Explicacion | None`. `tipo` es
  `trazo`, `pinyin` o `significado`; `error` es un `ErrorEvaluado` con el
  veredicto (`acerto`), el carácter, la respuesta del usuario, el detalle
  del catálogo, la dificultad y, para trazo, la secuencia y el veredicto de
  trazos-flask. Si la respuesta es correcta, devuelve `None`.
- `adaptadores/reglas.py` es el único adaptador: reglas fijas, sin red ni
  azar. La misma entrada da siempre la misma explicación.
- `adaptadores/fabrica.py` elige el adaptador según `EXPLICADOR_ERRORES`
  (por defecto `reglas`), igual que `PROVEEDOR_EJEMPLOS` en ejemplos-flask.
  Un valor desconocido detiene el arranque.
- Un adaptador con un modelo de lenguaje se puede sumar en `adaptadores/` y
  registrar en la fábrica sin tocar el dominio ni el caso de uso. No está
  implementado.
- La explicación es un extra: si el explicador lanza una excepción, se
  registra en el log y la respuesta sale sin `explicacion`.

`Explicacion` tiene `codigo` (estable: lo usan el frontend y las pruebas),
`titulo`, `porque` y `pista`. El bloque se muestra debajo del veredicto, así
que no lo repite: `titulo` dice dónde o qué parte; `porque`, una sola idea
(por qué importa o la causa probable) con palabras cotidianas, en dos frases
cortas como mucho; `pista`, una acción concreta con los datos reales (en
pinyin no repite la lectura que Práctica ya muestra, dice cómo
pronunciarla). Los textos se marcan con `N_` y se traducen al idioma de
la petición, como los mensajes de error.

### Catálogo de explicaciones

Solo aparecen cuando `acerto` es `false`.

| `codigo` | Tipo | Condición | Datos que usa |
|----------|------|-----------|---------------|
| `TRAZO_FUERA_DE_LUGAR` | trazo | `motivo` es `fuera_de_lugar` (el trazo está en otra parte del carácter) | `secuencia`; zona de inicio y dirección, calculadas con el primer y el último punto de la mediana |
| `TRAZO_INVERTIDO` | trazo | `motivo` es `invertido` | `secuencia`; zona de inicio y dirección, calculadas con el primer y el último punto de la mediana |
| `TRAZO_CORTO` | trazo | `motivo` es `incompleto` y `razon_longitud` menor que 1 | `secuencia`, `razon_longitud` (como porcentaje), zona del final |
| `TRAZO_LARGO` | trazo | `motivo` es `incompleto` y `razon_longitud` mayor o igual que 1 | `secuencia`, `razon_longitud`, zona del final |
| `TRAZO_INCOMPLETO` | trazo | `motivo` es `incompleto` sin `razon_longitud` (respaldo para un trazos-flask anterior) | `secuencia`, zonas de inicio y final |
| `TRAZO_IMPRECISO` | trazo | `motivo` es `impreciso` | `secuencia`; tramo del mayor desvío según `puntos_lejanos[0].posicion` (principio, medio o final); zona de inicio y dirección |
| `PINYIN_INICIAL` | pinyin | La final coincide con una lectura y la inicial no | Inicial escrita y esperada; lectura con tono |
| `PINYIN_FINAL` | pinyin | La inicial coincide con una lectura y la final no | Final escrita y esperada; lectura con tono |
| `PINYIN_DISTINTO` | pinyin | Cualquier otro caso (también vacía, varias sílabas o sin consonante inicial) | Lecturas con tono |
| `SIGNIFICADO_PARCIAL` | significado | Alguna palabra de la respuesta está en la definición (sin contar palabras vacías como "a", "the" o "to") | Palabras en común y el sentido que las contiene |
| `SIGNIFICADO_CERCANO` | significado | Similitud a 0.15 o menos del umbral, y el sentido más parecido tiene 4 letras o más | Definición |
| `SIGNIFICADO_DISTINTO` | significado | Cualquier otro caso, incluida una respuesta en español | Definición; la pista recuerda responder en inglés |

Notas sobre los datos:

- Zonas y dirección usan el sistema de Make Me a Hanzi (lienzo de 1024, eje
  Y hacia arriba). Las zonas son los tercios del lienzo ("arriba a la
  izquierda", "en el centro"...) y la dirección, una de ocho ("hacia abajo
  y a la izquierda"). En trazos con giro es una aproximación: describe el
  recorrido de punta a punta.
- `razon_longitud` llega de trazos-flask, pero no sale en la respuesta de
  evaluación: los campos de trazo siguen siendo los de v1.
- En pinyin se compara con la lectura más cercana: 长 con "chan" explica la
  final contra "cháng", no contra "zhǎng".
- `SIGNIFICADO_CERCANO` no aparece cuando lo más parecido es un sentido
  corto ("an", "one"), porque esos solo aceptan coincidencia exacta y
  "revisá la ortografía" sería engañoso.

### Nota de tono

El tono no se evalúa (ver "Reglas"), así que "hao" acierta para 好. Cuando
un pinyin acierta, la respuesta trae `nota` con `codigo` `PINYIN_TONO` y el
texto "Se lee hǎo, tercer tono." El tono sale de la marca de la lectura que
coincidió (sin marca, tono neutro). Si varias lecturas coinciden sin tono
(了: "liǎo" y "liào"), gana la que coincide con el tono escrito y, si no,
la primera del catálogo. `acerto` no cambia. Lo arma `dominio/notas.py`, no
el puerto: deducir el tono de la marca es un dato, no una explicación.

### Nota de mejora de un trazo aprobado

Un trazo aprobado como "aceptable" trae `puntos_lejanos` de trazos-flask
(los puntos que más se alejaron, con su `posicion` en el recorrido). En ese
caso la respuesta trae `nota` con `codigo` `TRAZO_MEJORA`; `acerto`,
`puntaje` y `motivo` no cambian. No aparece en un trazo correcto sin
`puntos_lejanos` ni en uno fallado (ese lleva `explicacion`).

- El tramo sale del punto con mayor `desvio`, con los mismos cortes que
  `TRAZO_IMPRECISO` (principio, medio o final).
- La dirección local se calcula con la mediana alrededor de ese punto (de
  `posicion - 0.15` a `posicion + 0.15` del recorrido, por longitud) y se
  compara con la dirección de punta a punta (`dominio/geometria.py`).
- Si difieren, el trazo gira en ese tramo: "Bien. Al final, el trazo gira
  hacia la derecha." (el trazo 2 de 人 dibujado recto hasta el final, sin
  aplanar). Al principio dice "sale" en vez de "gira".
- Si no difieren, solo se alejó de la guía: "Bien. Al final, seguí más cerca
  de la guía."
- Las direcciones son ocho sectores de 45 grados: un trazo casi recto cuya
  dirección cae justo en el borde de dos sectores puede leerse como giro.

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
| `EXPLICADOR_ERRORES` | `reglas`              | Adaptador que explica los errores; hoy solo `reglas` |
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
{"tipo": "significado", "caracter": "人", "acerto": true}
```

Al final, y solo cuando corresponde, dos campos opcionales (RF-IA-04):

- `nota` `{codigo, texto}` si la respuesta acierta: `PINYIN_TONO` en un
  pinyin, `TRAZO_MEJORA` en un trazo aprobado con un tramo desviado;
- `explicacion` `{codigo, titulo, porque, pista}` si `acerto` es `false`.

```json
{"tipo": "pinyin", "caracter": "好", "acerto": true,
 "nota": {"codigo": "PINYIN_TONO", "texto": "Se lee hǎo, tercer tono."}}

{"tipo": "pinyin", "caracter": "好", "acerto": false,
 "explicacion": {"codigo": "PINYIN_INICIAL",
                 "titulo": "Consonante inicial",
                 "porque": "La terminación ao está bien. Con otra letra al comienzo, ya es otra palabra.",
                 "pista": "Decilo en dos partes, h y ao, y después juntalas con el tercer tono."}}
```

Trazo responde `200` con el veredicto de trazos-flask, en el orden de
`ResultadoComparacionSerializer` de v1:

```json
{"tipo": "trazo", "caracter": "人", "acerto": true, "secuencia": 1,
 "aprobado": true, "puntaje": 100, "motivo": "correcto", "invertido": false,
 "detalle": "Trazo correcto.", "puntos_lejanos": []}
```

Un trazo fallado agrega `explicacion` al final, por ejemplo con
`"codigo": "TRAZO_INVERTIDO"` y la pista "Empezá arriba al centro y avanzá
hacia abajo y a la izquierda." Un trazo aprobado como "aceptable" puede
agregar `nota`, por ejemplo
`{"codigo": "TRAZO_MEJORA", "texto": "Bien. Al final, el trazo gira hacia la derecha."}`.

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
- El significado se compara también con cada sentido de la definición
  (RF-IA-04). En v1 un sentido correcto suelto fallaba: "good" para 好 daba
  0.17 contra la definición completa. Los umbrales son los mismos.
- El trazo no trae `distancia_media` (trazos-flask no la devuelve) ni
  `razon_longitud` (trazos-flask la devuelve, pero solo la usa el
  explicador de errores).
- Una dependencia caída da `503` en vez de un resultado falso.
- `explicacion` y `nota` (RF-IA-04) no existen en v1. Son opcionales y van
  al final: un cliente de v1 que solo lee `acerto` no cambia.

## Docker

```bash
docker build -t evaluacion-flask services/evaluacion-flask
docker run --rm -p 5087:5000 \
  -e CATALOGO_URL=http://host.docker.internal:5081 \
  -e TRAZOS_URL=http://host.docker.internal:5082 evaluacion-flask
```
