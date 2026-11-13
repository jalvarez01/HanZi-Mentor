# aliado-flask

Microservicio que consume el servicio del equipo aliado (T26): **VaultDrop**,
un simulador académico de apertura de cajas de otro equipo del curso
([github.com/jrestrepoc/VaultDrop](https://github.com/jrestrepoc/VaultDrop)).

En la app aparece en Inicio como la sección **"Caja de VaultDrop"**: el
estudiante elige una caja y la abre. El ítem sale con las probabilidades que
publica VaultDrop.

Cumple el estándar de los servicios Flask
([`docs/arquitectura/estandar-flask.md`](../../docs/arquitectura/estandar-flask.md)):
Dockerfile propio, `GET /health`, errores en JSON, pruebas con pytest,
mensajes en español e inglés según `Accept-Language` y ningún `import django`.
No guarda estado: no tiene base de datos.

## Qué consume de VaultDrop

`GET /api/v2/catalogo/`, el catálogo público de su microservicio Flask (detrás
de su Nginx). No pide login ni créditos. Responde las cajas activas, cada una
con sus ítems y la probabilidad de cada ítem:

```json
[{"id": 7, "nombre": "Caja Dragón", "imagen_url": "", "descripcion": "", "precio": "25.00", "activa": true,
  "items": [{"item": {"id": 1, "nombre": "AK-47 | Redline", "imagen_url": "/static/...", "rareza": "classified", "valor_estimado": "85.00"},
             "probabilidad": "60.00"}]}]
```

Abrir una caja de verdad en VaultDrop (`POST /api/v1/cajas/<id>/abrir/`) exige
una cuenta y gasta créditos. Por eso aquí abrir es un **sorteo con las mismas
probabilidades**: no usa cuentas de VaultDrop y no guarda nada.

## Rutas

Bajo `/api/v2/aliado/`, publicadas en Nginx. El navegador nunca llama a
VaultDrop directo: así ellos no necesitan configurar CORS y el respaldo es
nuestro.

| Método | Ruta | Qué hace |
|--------|------|----------|
| GET | `cajas/` | Cajas activas de VaultDrop, con cuántos ítems tiene cada una |
| POST | `cajas/<id>/abrir/` | Sortea un ítem de la caja con sus probabilidades |

```json
{"aliado": "VaultDrop", "proveedor": "vaultdrop", "respaldo": false,
 "caja": {"id": 7, "nombre": "Caja Dragón", "precio": "25.00", "imagen_url": ""},
 "item": {"nombre": "AK-47 | Redline", "rareza": "classified", "valor_estimado": "85.00",
          "imagen_url": "http://<IP de VaultDrop>/static/...", "probabilidad": "60.00"}}
```

- `proveedor` dice qué adaptador respondió: `vaultdrop` o `falso`.
- `respaldo: true` quiere decir que VaultDrop no respondió y se usó el último
  catálogo que sí respondió.
- Las imágenes llegan con ruta relativa y se completan con la URL del aliado.

| Estado | `codigo` | Cuándo |
|-------:|----------|--------|
| 404 | `NO_ENCONTRADO` | La caja no existe |
| 409 | `CAJA_SIN_ITEMS` | La caja no tiene ítems con probabilidad mayor que cero |
| 503 | `ALIADO_NO_DISPONIBLE` | VaultDrop no respondió y no hay ningún catálogo guardado |

## Patrón Adapter

```
servicio.py ──> ProveedorCajas (dominio/puertos.py, el puerto)
                     ▲
                     ├── AdaptadorVaultDrop (adaptadores/vaultdrop.py)
                     └── CajasFalsas        (adaptadores/falso.py)
adaptadores/fabrica.py elige el adaptador con ALIADO_PROVEEDOR
```

Si VaultDrop cambia su API, o se cambia de aliado, solo cambia el adaptador.

## Resiliencia

- **Espera máxima:** `ALIADO_TIMEOUT` segundos (6 por defecto).
- **Catálogo guardado:** el último que respondió se reutiliza 60 s sin volver
  a llamar a VaultDrop. Después se pide otra vez y, si VaultDrop no responde,
  se usa el guardado con `respaldo: true`. En la app aparece un aviso.
- **Sin ningún catálogo:** 503 traducido. La sección muestra el error con
  "Reintentar" y el resto de Inicio sigue igual.
- **Imágenes:** la imagen del premio solo se muestra si carga; si VaultDrop no
  la sirve, no queda un ícono roto.
- **Un proceso con hilos:** el catálogo guardado vive en memoria, así que
  gunicorn corre con 1 proceso y 4 hilos para que todas las peticiones
  compartan el mismo respaldo.

## Configuración

| Variable | Por defecto | Para qué |
|----------|-------------|----------|
| `ALIADO_PROVEEDOR` | `falso` (en el compose, `vaultdrop`) | `vaultdrop` (su catálogo real) o `falso` (dos cajas fijas sin red) |
| `ALIADO_URL` | vacía (en el compose, `http://3.217.19.101`) | URL base de VaultDrop sin `/api`: su IP elástica. Obligatoria con `vaultdrop` |
| `ALIADO_TIMEOUT` | `6` | Segundos de espera. VaultDrop a veces tarda más de 3 s (se midieron 4,4 s) |

`docker-compose.yml` ya trae la IP elástica de VaultDrop, que nos pasó su
equipo: en EC2 no hay que tocar el `.env`. Si la IP cambia, se pone la nueva
en `ALIADO_URL` del `.env` y `docker compose up -d flask_aliado`.

VaultDrop usa cuatro rarezas: `COMUN`, `RARO`, `EPICO` y `LEGENDARIO`. El
frontend las traduce y les da un color; una rareza nueva se muestra tal cual.

## Pruebas

```bash
docker build -t aliado-flask services/aliado-flask
docker run --rm -u root --entrypoint python aliado-flask -m pytest -q -p no:cacheprovider
```

26 pruebas:
- el adaptador con el formato real de VaultDrop (de `services/catalog_service/repository.py` en su repo), sin red;
- el sorteo con sus probabilidades;
- el respaldo con el último catálogo, que se reutiliza 60 s también cuando el último intento falló;
- las rutas, los errores en es y en, y que todos los textos tengan traducción.

Además se probó de punta a punta contra el VaultDrop real
(`http://3.217.19.101`: 4 cajas, imágenes y rarezas), y con un VaultDrop de
prueba que respondía el mismo JSON en cuatro casos:
1. VaultDrop arriba;
2. VaultDrop caído con catálogo guardado (`respaldo: true`);
3. VaultDrop caído desde el arranque (503 y "Reintentar");
4. VaultDrop de vuelta ("Reintentar" se recupera).
