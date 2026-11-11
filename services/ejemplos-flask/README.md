# ejemplos-flask

Microservicio que devuelve oraciones de ejemplo en chino para un carácter,
con pinyin y traducción. Consume la API pública de
[Tatoeba](https://api.tatoeba.org) mediante el **patrón Adapter** con
Inversión de Dependencias (Entrega 2, tarea T15). Sigue el
[estándar Flask](../../docs/arquitectura/estandar-flask.md) del proyecto y no
guarda estado.

## Cómo está armado el Adapter

```
rutas.py ──> servicio.py ──> dominio/puertos.py  (ProveedorEjemplos, interfaz)
                                    ▲
                                    │ implementan
                          adaptadores/tatoeba.py (API de Tatoeba, por defecto)
                          adaptadores/falso.py   (datos fijos, sin red)

app.py ──> adaptadores/fabrica.py: elige el adaptador según PROVEEDOR_EJEMPLOS
```

| Archivo                  | Responsabilidad                                                    |
|--------------------------|--------------------------------------------------------------------|
| `dominio/ejemplo.py`     | Entidad `Ejemplo` (texto, pinyin, traducción)                      |
| `dominio/puertos.py`     | Puerto `ProveedorEjemplos` y la excepción `ProveedorNoDisponible`  |
| `adaptadores/tatoeba.py` | Adaptador real: llama a Tatoeba y traduce su respuesta a `Ejemplo` |
| `adaptadores/falso.py`   | Adaptador con datos fijos, para pruebas y demos sin internet       |
| `adaptadores/fabrica.py` | Único lugar que conoce los adaptadores concretos                   |
| `servicio.py`            | Caso de uso `buscar_ejemplos`: solo conoce el puerto               |
| `validacion.py`          | Forma de la entrada (`hanzi`, `lang`, `limite`)                    |
| `rutas.py`               | `GET /api/v2/ejemplos/<hanzi>/`                                    |
| `app.py`                 | Fábrica `create_app`, raíz de composición y `GET /health`          |

El caso de uso nunca importa un adaptador: recibe el que la fábrica eligió.
Cambiar de proveedor es agregar un archivo en `adaptadores/`, registrarlo en
la fábrica y cambiar `PROVEEDOR_EJEMPLOS`; el dominio y las rutas no cambian.

## Qué hace el adaptador de Tatoeba

Llama a `GET https://api.tatoeba.org/v1/sentences`, el endpoint estable de la
API (no requiere clave), pidiendo oraciones en chino (`lang=cmn`) que
contengan el carácter y tengan traducción al idioma pedido. Después:

- Si la oración está en chino tradicional, usa la versión simplificada que
  Tatoeba trae como transcripción.
- Toma el pinyin con tildes (`Xuéxí ba.`), no la versión con números (`Xue2xi2 ba5.`).
- Pide primero solo oraciones con traducción directa al idioma pedido. Las
  indirectas pasan por un tercer idioma y pierden sentido (等一下, "espera un
  momento", llegaba como "Err..."); solo se aceptan si no hay ninguna directa.
- Descarta las frases repetidas (la misma oración en simplificado y en tradicional).
- Si Tatoeba no responde en `TATOEBA_TIMEOUT` segundos, o responde algo
  inesperado, lanza `ProveedorNoDisponible` y el servicio responde `503`.

Las oraciones de Tatoeba tienen licencia CC BY 2.0 FR: la respuesta incluye
`atribucion` para que el frontend muestre el crédito.

## Ejecutar

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q

# Incluye una prueba contra la API real de Tatoeba
TATOEBA_EN_VIVO=1 .venv/bin/pytest -q

# Desarrollo
.venv/bin/python app.py

# Docker
docker build -t ejemplos-flask .
docker run --rm -p 5000:5000 ejemplos-flask

# Sin internet, con datos fijos
docker run --rm -p 5000:5000 -e PROVEEDOR_EJEMPLOS=falso ejemplos-flask
```

## Contrato

### `GET /api/v2/ejemplos/<hanzi>/`

| Parámetro | Valores           | Por defecto |
|-----------|-------------------|-------------|
| `hanzi`   | 1 a 4 caracteres chinos (en la ruta) | — |
| `lang`    | `es`, `en`        | `es`        |
| `limite`  | 1 a 10            | 5           |

```bash
curl -s "http://localhost:5000/api/v2/ejemplos/学/?lang=es&limite=2"
```

Respuesta `200`:

```json
{
  "hanzi": "学",
  "idioma": "es",
  "proveedor": "tatoeba",
  "atribucion": "Oraciones de Tatoeba.org (CC BY 2.0 FR)",
  "ejemplos": [
    {"texto": "学吧！", "pinyin": "Xué ba!", "traduccion": "Estudiad."},
    {"texto": "学习吧。", "pinyin": "Xuéxí ba.", "traduccion": "Aprende."}
  ]
}
```

Si no hay ejemplos, `ejemplos` es una lista vacía. `pinyin` y `traduccion`
pueden ser `null` cuando el proveedor no los trae, y `atribucion` es `null`
con el adaptador falso.

Errores (siempre JSON):

| Estado | `codigo`                  | Cuándo                                        |
|--------|---------------------------|-----------------------------------------------|
| 400    | `ENTRADA_INVALIDA`        | `hanzi`, `lang` o `limite` fuera de contrato  |
| 404    | `NO_ENCONTRADO`           | Ruta inexistente                              |
| 405    | `METODO_NO_PERMITIDO`     | Método HTTP no soportado                      |
| 503    | `PROVEEDOR_NO_DISPONIBLE` | La API externa no respondió                   |
| 500    | `ERROR_INTERNO`           | Error inesperado (sin stack trace)            |

### `GET /health`

`200 {"estado": "ok", "servicio": "ejemplos-flask"}`

## Variables de entorno

| Variable             | Default          | Uso                                  |
|----------------------|------------------|--------------------------------------|
| `SERVICE_NAME`       | `ejemplos-flask` | Nombre que devuelve `/health`        |
| `HOST`               | `0.0.0.0`        | Interfaz de `python app.py`          |
| `PORT`               | `5000`           | Puerto de `python app.py`            |
| `FLASK_DEBUG`        | `0`              | `1` activa debug, solo en local      |
| `PROVEEDOR_EJEMPLOS` | `tatoeba`        | Adaptador que se inyecta (`tatoeba` o `falso`) |
| `TATOEBA_URL`        | `https://api.tatoeba.org` | URL base de la API de Tatoeba |
| `TATOEBA_TIMEOUT`    | `3`              | Segundos de espera antes de responder 503 |

## Pendiente

- Registro en `docker-compose.yml` (`flask_ejemplos`) y en `nginx.conf`
  (`location /api/v2/ejemplos/`), coordinado con la infraestructura de la Entrega 2.
