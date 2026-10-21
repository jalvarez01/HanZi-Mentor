# trazos-flask

Microservicio Flask que valida trazos dibujados contra la mediana oficial del
carácter. Es la primera pieza extraída del monolito Django con el Strangler
Pattern (taller 02): la lógica de `comparador.py` es una copia del dominio de
`services/contenido/caracteres/domain/comparador.py`, sin dependencias de Django.

## Estructura

| Archivo         | Responsabilidad                                              |
|-----------------|--------------------------------------------------------------|
| `app.py`        | Fábrica `create_app()`: config, rutas, manejadores, `/health` |
| `config.py`     | Configuración desde variables de entorno                     |
| `rutas.py`      | Controlador: lee el JSON, delega y responde                  |
| `validacion.py` | Valida la forma de la entrada (`EntradaInvalida` → 400)      |
| `servicio.py`   | Caso de uso: invoca `comparar_trazo()` y arma el resultado   |
| `comparador.py` | Lógica de comparación (dominio puro)                         |
| `errores.py`    | Manejadores globales; todo error responde JSON               |

## Ejecutar

```bash
cd services/trazos-flask
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Desarrollo
python app.py

# Producción
gunicorn -w 2 -b 0.0.0.0:5000 "app:create_app()"
```

Variables de entorno:

| Variable      | Default   | Uso                                     |
|---------------|-----------|-----------------------------------------|
| `PORT`        | `5000`    | Puerto de `python app.py`               |
| `HOST`        | `0.0.0.0` | Interfaz de escucha                     |
| `FLASK_DEBUG` | `0`       | `1` activa el modo debug (solo en local) |
| `MAX_PUNTOS`  | `5000`    | Máximo de puntos por lista              |
| `SERVICE_NAME`| `trazos-flask` | Nombre que devuelve `/health`      |

Ver `.env.example`. El servicio sigue el estándar de `services/flask-base`;
como no guarda estado, no usa `DATABASE_URL`.

## Pruebas

```bash
pytest -v
```

## Contrato

### `POST /api/v2/trazos/validar/`

Entrada: `mediana` y `puntos` son listas de al menos 2 puntos, cada uno como
`[x, y]` o `{"x": .., "y": ..}`. `ancho` y `alto` son enteros positivos (el
tamaño del lienzo donde se dibujó).

```bash
curl -s -X POST http://localhost:5000/api/v2/trazos/validar/ \
  -H "Content-Type: application/json" \
  -d '{
        "mediana": [[458,800],[435,764],[400,700],[350,620],[300,540]],
        "puntos":  [[134,29],[127,40],[117,59],[103,82],[88,105]],
        "ancho": 300,
        "alto": 300
      }'
```

Respuesta `200`:

```json
{"aprobado": true, "puntaje": 100, "motivo": "correcto", "detalle": "Trazo correcto.",
 "invertido": false, "puntos_lejanos": []}
```

Errores (siempre JSON):

| Estado | `codigo`              | Cuándo                                |
|--------|-----------------------|---------------------------------------|
| 400    | `ENTRADA_INVALIDA`    | JSON mal formado o fuera de contrato  |
| 404    | `NO_ENCONTRADO`       | Ruta inexistente                      |
| 405    | `METODO_NO_PERMITIDO` | Método HTTP no soportado              |
| 500    | `ERROR_INTERNO`       | Error inesperado (sin stack trace)    |

### `GET /health`

```bash
curl -s http://localhost:5000/health
# {"estado":"ok","servicio":"trazos-flask"}
```
