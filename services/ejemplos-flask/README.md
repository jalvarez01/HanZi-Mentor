# ejemplos-flask

Microservicio que devuelve oraciones de ejemplo en chino para un carácter,
con pinyin y traducción. Consume una API de terceros mediante el **patrón
Adapter** con Inversión de Dependencias (Entrega 2, tarea T15). Sigue el
[estándar Flask](../../docs/arquitectura/estandar-flask.md) del proyecto y no
guarda estado.

## Cómo está armado el Adapter

```
rutas.py ──> servicio.py ──> dominio/puertos.py  (ProveedorEjemplos, interfaz)
                                    ▲
                                    │ implementan
                          adaptadores/falso.py   (datos fijos, sin red)
                          adaptadores/<real>.py  (API externa, por elegir)

app.py ──> adaptadores/fabrica.py: elige el adaptador según PROVEEDOR_EJEMPLOS
```

| Archivo                  | Responsabilidad                                                    |
|--------------------------|--------------------------------------------------------------------|
| `dominio/ejemplo.py`     | Entidad `Ejemplo` (texto, pinyin, traducción)                      |
| `dominio/puertos.py`     | Puerto `ProveedorEjemplos` y la excepción `ProveedorNoDisponible`  |
| `adaptadores/falso.py`   | Adaptador con datos fijos, para pruebas y demos sin internet       |
| `adaptadores/fabrica.py` | Único lugar que conoce los adaptadores concretos                   |
| `servicio.py`            | Caso de uso `buscar_ejemplos`: solo conoce el puerto               |
| `validacion.py`          | Forma de la entrada (`hanzi`, `lang`, `limite`)                    |
| `rutas.py`               | `GET /api/v2/ejemplos/<hanzi>/`                                    |
| `app.py`                 | Fábrica `create_app`, raíz de composición y `GET /health`          |

El caso de uso nunca importa un adaptador: recibe el que la fábrica eligió.
Cambiar de proveedor es agregar un archivo en `adaptadores/`, registrarlo en
la fábrica y cambiar `PROVEEDOR_EJEMPLOS`; el dominio y las rutas no cambian.

## Ejecutar

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q

# Desarrollo
.venv/bin/python app.py

# Docker
docker build -t ejemplos-flask .
docker run --rm -p 5000:5000 ejemplos-flask
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
  "proveedor": "falso",
  "ejemplos": [
    {"texto": "我学中文。", "pinyin": "wǒ xué zhōngwén", "traduccion": "Estudio chino."},
    {"texto": "他是学生。", "pinyin": "tā shì xuésheng", "traduccion": "Él es estudiante."}
  ]
}
```

Si no hay ejemplos, `ejemplos` es una lista vacía. `pinyin` y `traduccion`
pueden ser `null` cuando el proveedor no los trae.

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
| `PROVEEDOR_EJEMPLOS` | `falso`          | Adaptador que se inyecta (`falso`)   |

## Pendiente

- Adaptador real de la API de terceros, cuando el equipo elija el proveedor (T02).
- Registro en `docker-compose.yml` (`flask_ejemplos`) y en `nginx.conf`
  (`location /api/v2/ejemplos/`), coordinado con la infraestructura de la Entrega 2.
