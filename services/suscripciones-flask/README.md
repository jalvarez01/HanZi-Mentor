# suscripciones-flask

Microservicio de suscripciones de HanZi Mentor (RF-USR-01, issue #2): planes
Free y Premium, con activación, renovación y cancelación. El cobro pasa por
una pasarela de pago detrás del patrón Adapter; hoy la única es
**simulada**: no mueve dinero ni sale a internet.

Cumple el estándar de los servicios Flask
([`docs/arquitectura/estandar-flask.md`](../../docs/arquitectura/estandar-flask.md)):
Dockerfile propio, base propia (`db_suscripciones`), `GET /health`, errores
en JSON, pruebas con pytest, mensajes en español e inglés según
`Accept-Language` y ningún `import django`.

## Planes

| Plan | Precio | Niveles | Cómo se obtiene |
|------|-------:|---------|-----------------|
| Free (`free`) | 0 | HSK 1 a 3 | Por defecto: lo tiene todo usuario que nunca pagó, y se vuelve a él cuando Premium vence |
| Premium (`premium`) | 14 900 COP por 30 días | HSK 1 a 6 | Se activa pagando |

El frontend usa `nivel_maximo` para poner el candado en HSK 4 a 6 de
Practicar (sesiones y lecciones).

## Ciclo de vida

| Estado | Plan que rige | Acciones posibles |
|--------|---------------|-------------------|
| Nunca pagó | free | activar |
| Premium activa | premium | renovar (*), cancelar |
| Premium cancelada | premium hasta `vence_en` | renovar (*) |
| Premium vencida | free | activar |

(*) Solo si faltan 7 días o menos para el vencimiento
(`VENTANA_RENOVACION_DIAS` en `dominio/planes.py`). Así no se puede renovar
justo después de activar o de renovar, y un doble clic no cobra dos periodos
seguidos. Una suscripción cancelada puede renovarse cuando entra en esa
ventana; antes no tiene ninguna acción. Fuera de la ventana, renovar
responde 409 `RENOVACION_ANTICIPADA`. Cada periodo sigue siendo de 30 días.

- **Renovar** suma 30 días a lo que queda y anula una cancelación.
- **Cancelar** no devuelve dinero: Premium sigue hasta `vence_en`.
- **Vencida** no se guarda: se calcula con `vence_en`, así que no hace falta
  ningún proceso que pase a cambiar el estado.

Las reglas están en `dominio/suscripcion.py`, sin Flask ni SQLAlchemy.

## Rutas

Todas bajo `/api/v2/suscripciones/`, publicadas en Nginx.

| Método | Ruta | Qué hace | Respuesta |
|--------|------|----------|-----------|
| GET | `planes/` | Catálogo de planes | 200 |
| GET | `<usuario_id>/` | Plan que rige hoy | 200 (Free si nunca pagó) |
| POST | `<usuario_id>/activar/` | Cobra y activa Premium | 201 |
| POST | `<usuario_id>/renovar/` | Cobra otro periodo | 200 |
| POST | `<usuario_id>/cancelar/` | Cancela sin reembolso | 200 |
| GET | `<usuario_id>/pagos/` | Historial de cobros (hasta 20) | 200 |

```bash
U=3fa85f64-5717-4562-b3fc-2c963f66afa6
curl http://localhost/api/v2/suscripciones/$U/
curl -X POST http://localhost/api/v2/suscripciones/$U/activar/ \
  -H "Content-Type: application/json" \
  -d '{"plan": "premium", "pago": {"numero": "4242 4242 4242 4242", "titular": "Ana Pérez", "vencimiento": "12/30", "cvc": "123"}}'
```

Estado del plan:

```json
{
  "usuario_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "plan": "premium",
  "nombre_plan": "Premium",
  "estado": "activa",
  "vence_en": "2026-12-11T15:00:00Z",
  "nivel_maximo": 6,
  "acciones": ["cancelar"],
  "renovable_desde": "2026-12-04T15:00:00Z"
}
```

`renovable_desde` es `vence_en` menos la ventana de renovación (7 días), en
el mismo formato que `vence_en`: desde esa fecha aparece `renovar` en
`acciones`. Solo tiene valor en un Premium vigente, activo o cancelado; en
Free, vencida o sin suscripción es `null`. Va al final, así que las demás
claves conservan su orden. El panel de plan lo usa para decir "Podrás
renovar desde el ..." mientras `renovar` todavía no está disponible.

`activar` y `renovar` responden `{"suscripcion": {...}, "pago": {...}}`.
El pago trae `referencia`, `monto`, `moneda`, `marca` y `ultimos4`: el número
completo, el CVC y el titular **nunca se guardan ni se devuelven**.

### Errores

| Estado | `codigo` | Cuándo |
|-------:|----------|--------|
| 400 | `ENTRADA_INVALIDA` | UUID, plan o tarjeta inválidos (número con Luhn, MM/AA, CVC, titular) |
| 402 | `TARJETA_RECHAZADA`, `FONDOS_INSUFICIENTES` | La pasarela no aprobó el cobro. Queda en el historial como `rechazado` |
| 409 | `YA_ES_PREMIUM`, `SIN_PREMIUM`, `YA_CANCELADA`, `RENOVACION_ANTICIPADA` | La acción no se puede hacer desde el estado actual |
| 503 | `PASARELA_NO_DISPONIBLE` | La pasarela no respondió. No se guarda nada |

## Pasarela de pago (patrón Adapter)

```
servicio.py ──> PasarelaPago (pasarelas/base.py, el puerto)
                     ▲
                     └── PasarelaSimulada (pasarelas/simulada.py)
pasarelas/fabrica.py elige el adaptador con PASARELA_PAGO
```

Tarjetas de prueba de la pasarela simulada (los mismos números de prueba
que usa Stripe):

| Número | Resultado |
|--------|-----------|
| 4242 4242 4242 4242 (o cualquier otro válido) | Aprobada |
| 4000 0000 0000 0002 | 402 `TARJETA_RECHAZADA` |
| 4000 0000 0000 9995 | 402 `FONDOS_INSUFICIENTES` |
| 4000 0000 0000 0119 | 503 `PASARELA_NO_DISPONIBLE` |

Para una pasarela real (Wompi, Stripe...) basta un adaptador nuevo que
implemente `cobrar()` y registrarlo en `fabrica.py`. En ese caso la tarjeta
no debería pasar por este servicio: el frontend la tokenizaría con el SDK de
la pasarela y aquí llegaría solo el token.

## Límites conocidos

- **El candado de HSK 4 a 6 está en el frontend.** `flask_sesiones` y
  `flask_catalogo` todavía no consultan este servicio antes de armar una
  sesión o una lección. El siguiente paso es que lo hagan por HTTP, con el
  mismo modo degradado.
- **Modo degradado:** si este servicio no responde, el frontend no bloquea
  ningún nivel y avisa que no pudo confirmar el plan.
- **Sin renovación automática:** renovar es manual. Hacerla automática
  necesita una tarea programada (Celery beat) y una pasarela real.
- **Cobro y base no son una sola transacción:** se cobra primero y se guarda
  después. Con la pasarela simulada no importa; con una real habría que
  registrar el pago como pendiente antes de cobrar.

## Correr las pruebas

```bash
cd services/suscripciones-flask
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
```

O dentro de la imagen, sin instalar nada:

```bash
docker build -t suscripciones-flask services/suscripciones-flask
docker run --rm --entrypoint python suscripciones-flask -m pytest -q -p no:cacheprovider
```

67 pruebas: dominio, pasarela, validación de la tarjeta, flujos completos por
HTTP, idioma y el estándar común.
