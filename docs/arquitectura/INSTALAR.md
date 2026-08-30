# Instalación de las cuatro mejoras

Los cuatro pendientes quedaron resueltos: responder ejercicios, agente LangGraph,
repaso espaciado y catálogo desde el servicio `contenido`.

Verificado en local: **19 tests pasan** y el flujo completo responde por HTTP.

---

## Dónde va cada archivo

### Servicio `agente-tutor`

| Archivo descargado | Destino |
|---|---|
| `agente-tutor/models.py` | `services/agente-tutor/tutor/models.py` |
| `agente-tutor/services.py` | `services/agente-tutor/tutor/services.py` |
| `agente-tutor/views.py` | `services/agente-tutor/tutor/views.py` |
| `agente-tutor/urls.py` | `services/agente-tutor/tutor/urls.py` |
| `agente-tutor/serializers.py` | `services/agente-tutor/tutor/serializers.py` |
| `agente-tutor/repositories.py` | `services/agente-tutor/tutor/repositories.py` |
| `agente-tutor/tests.py` | `services/agente-tutor/tutor/tests.py` |
| `agente-tutor/progreso-models.py` | `services/agente-tutor/progreso/models.py` |
| `agente-tutor/domain/repaso.py` | `services/agente-tutor/tutor/domain/repaso.py` |
| `agente-tutor/domain/exceptions.py` | `services/agente-tutor/tutor/domain/exceptions.py` |
| `agente-tutor/infra/catalogo.py` | `services/agente-tutor/tutor/infra/catalogo.py` |
| `agente-tutor/infra/motores.py` | `services/agente-tutor/tutor/infra/motores.py` |
| `agente-tutor/infra/factories.py` | `services/agente-tutor/tutor/infra/factories.py` |
| `agente-tutor/agent/graph.py` | `services/agente-tutor/tutor/agent/graph.py` |

### Servicio `contenido`

| Archivo descargado | Destino |
|---|---|
| `contenido/models.py` | `services/contenido/caracteres/models.py` |
| `contenido/views.py` | `services/contenido/caracteres/views.py` |
| `contenido/urls.py` | `services/contenido/caracteres/urls.py` |
| `contenido/serializers.py` | `services/contenido/caracteres/serializers.py` |
| `contenido/admin.py` | `services/contenido/caracteres/admin.py` |
| `contenido/hsk.py` | `services/contenido/caracteres/hsk.py` |
| `contenido/config-urls.py` | `services/contenido/config/urls.py` |
| `contenido/commands/cargar_hanzi.py` | `services/contenido/caracteres/management/commands/cargar_hanzi.py` |

---

## Pasos

### 1. Crear las carpetas del management command

```bash
cd services/contenido
mkdir -p caracteres/management/commands
touch caracteres/management/__init__.py
touch caracteres/management/commands/__init__.py
```

Sin esos dos `__init__.py`, Django no encuentra el comando.

### 2. Instalar `requests` en agente-tutor

```bash
cd services/agente-tutor && source venv/bin/activate
pip install requests
pip freeze > requirements.txt
```

### 3. Migrar los dos servicios

```bash
cd services/agente-tutor && source venv/bin/activate
python manage.py makemigrations
python manage.py migrate
python manage.py test tutor
deactivate

cd ../contenido && source venv/bin/activate
python manage.py makemigrations
python manage.py migrate
deactivate
```

Deben salir 19 tests OK.

### 4. Cargar caracteres reales (opcional)

Con el fork de Make Me a Hanzi clonado en alguna carpeta:

```bash
cd services/contenido && source venv/bin/activate
python manage.py cargar_hanzi --ruta /ruta/a/makemeahanzi --nivel 1 2
```

El comando lee `dictionary.txt` y `graphics.txt`, filtra solo los caracteres de
los niveles pedidos y llena `Caracter` + `Trazo`. No necesita el resto del repo.

### 5. Levantar los dos servicios

```bash
# terminal 1
cd services/contenido && source venv/bin/activate
python manage.py runserver 8002

# terminal 2
cd services/agente-tutor && source venv/bin/activate
CATALOGO=REMOTO CONTENIDO_URL=http://localhost:8002 python manage.py runserver 8003
```

---

## Endpoints

### Crear sesión

```
POST http://localhost:8003/api/sesiones/
{"usuario_id": "...", "nivel_hsk": 2}
```

### Responder un ejercicio

```
POST http://localhost:8003/api/ejercicios/3/responder/
{"acerto": true}
```

Respuesta:

```json
{
  "ejercicio": {"id": 3, "caracter": "学", "es_refuerzo": false},
  "sesion_completada": false,
  "pendientes": 5,
  "proximo_repaso": "2026-08-16T03:07:05Z",
  "tasa_acierto": 0.73
}
```

### Consultar caracteres

```
GET http://localhost:8002/api/caracteres/?nivel=2&excluir=学&limite=4
GET http://localhost:8002/api/caracteres/学/
```

El detalle incluye los trazos en orden, con su path SVG y su mediana.

---

## Variables de entorno

```bash
TUTOR_ENGINE=MOCK          # MOCK | REAL
NOTIFICADOR=CONSOLE        # CONSOLE | EMAIL
CATALOGO=LOCAL             # LOCAL | REMOTO
CONTENIDO_URL=http://localhost:8002
ANTHROPIC_API_KEY=         # solo si TUTOR_ENGINE=REAL
TUTOR_MODEL=claude-sonnet-4-6
```

Los valores por defecto (todo en modo local/mock) hacen que el servicio arranque
sin configurar nada.

---

## Commits sugeridos

```bash
git add services/agente-tutor/tutor/domain/repaso.py
git commit -m "calculo del proximo repaso con intervalos que crecen"

git add services/agente-tutor/tutor/models.py services/agente-tutor/progreso/models.py
git commit -m "agrego campos para saber si un ejercicio ya se respondio"

git add services/agente-tutor/tutor/services.py services/agente-tutor/tutor/repositories.py
git commit -m "servicio para responder ejercicios y actualizar el progreso"

git add services/agente-tutor/tutor/views.py services/agente-tutor/tutor/urls.py services/agente-tutor/tutor/serializers.py services/agente-tutor/tutor/domain/exceptions.py
git commit -m "expongo el endpoint de responder ejercicio"

git add services/agente-tutor/tutor/agent/graph.py
git commit -m "el agente de langgraph que faltaba, con heuristica de respaldo"

git add services/agente-tutor/tutor/infra/
git commit -m "saco los caracteres hardcodeados del motor a un catalogo"

git add services/contenido/caracteres/ services/contenido/config/urls.py
git commit -m "modelos y api de caracteres en el servicio de contenido"

git add services/agente-tutor/tutor/tests.py
git commit -m "pruebas del repaso, las respuestas y el catalogo"

git add services/*/migrations services/*/*/migrations
git commit -m "migraciones"
```
