# HanZi Mentor 

Plataforma de aprendizaje de mandarín con tutor IA adaptativo. Enseña el orden correcto de trazos de los caracteres (hanzi), genera ejercicios personalizados según los errores reales de cada estudiante, y aplica repaso espaciado adaptativo.

**Proyecto académico** — SI3001 Arquitectura de Software, Universidad EAFIT.

---

## Arquitectura

```
HanZi-Mentor/
├── services/
│   ├── usuarios/          # Django — cuentas, autenticación, suscripciones
│   ├── contenido/         # Django — caracteres, trazos, lecciones, vocabulario
│   └── agente-tutor/      # Django — agente IA, progreso, curva de olvido
├── gateway/               # API Gateway
├── frontend/              # React + Vite (PWA mobile-first)
├── shared/                # Eventos, esquemas y utilidades compartidas
├── infra/                 # Docker, nginx, scripts
└── docs/                  # Arquitectura, diagramas, entregas
```

Cada servicio es un proyecto Django independiente con su propia base de datos y su propio entorno virtual.

---

## Requisitos previos

| Herramienta | Versión mínima | Para qué |
|---|---|---|
| Python | 3.10+ | Backend (Django) |
| Node.js | 18+ | Frontend (React + Vite) |
| Git | cualquiera | Control de versiones |

### Instalar los requisitos

<details>
<summary><b>Windows</b></summary>

**Opción recomendada — con winget** (viene incluido en Windows 10/11):

```powershell
winget install Python.Python.3.12
winget install OpenJS.NodeJS.LTS
winget install Git.Git
```

**Opción manual:** descargar los instaladores de [python.org](https://www.python.org/downloads/), [nodejs.org](https://nodejs.org/) y [git-scm.com](https://git-scm.com/download/win).

> Al instalar Python, marcá la casilla **"Add Python to PATH"** o los comandos no funcionarán en la terminal.

Cerrá y volvé a abrir PowerShell después de instalar.

</details>

<details>
<summary><b>macOS</b></summary>

**Opción recomendada — con Homebrew:**

```bash
# Instalar Homebrew si no lo tenés
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install python@3.12 node git
```

**Opción manual:** descargar los instaladores desde [python.org](https://www.python.org/downloads/macos/) y [nodejs.org](https://nodejs.org/).

</details>

<details>
<summary><b>Linux (Ubuntu / Debian)</b></summary>

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git curl

# Node.js 20 LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

**Fedora / RHEL:**

```bash
sudo dnf install -y python3 python3-pip git nodejs npm
```

**Arch:**

```bash
sudo pacman -S python python-pip git nodejs npm
```

</details>

### Verificar la instalación

```bash
python3 --version    # Windows: python --version
node --version
npm --version
git --version
```

---

## Instalación del proyecto

### 1. Clonar el repositorio

```bash
git clone https://github.com/jalvarez01/HanZi-Mentor.git
cd HanZi-Mentor
```

### 2. Levantar los servicios backend

Cada servicio necesita su propio entorno virtual. Repetí estos pasos para `usuarios`, `contenido` y `agente-tutor`.

<details open>
<summary><b>macOS / Linux</b></summary>

```bash
cd services/usuarios

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

python manage.py migrate
python manage.py runserver 8001
```

</details>

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
cd services\usuarios

python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt

python manage.py migrate
python manage.py runserver 8001
```

> Si PowerShell bloquea el script de activación, ejecutá una vez:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

**Con CMD** en lugar de PowerShell, la activación es:
```cmd
venv\Scripts\activate.bat
```

</details>

Puertos sugeridos para no chocar entre servicios:

| Servicio | Puerto |
|---|---|
| `usuarios` | 8001 |
| `contenido` | 8002 |
| `agente-tutor` | 8003 |

Para salir del entorno virtual: `deactivate`.

**API Gateway (opcional, en local):** el frontend puede pegarle directo a
cada puerto como se explicó arriba, o pasar por el gateway de
`infra/nginx/nginx.conf`, que expone todo en un solo puerto (8080) y
rutea por prefijo al servicio dueño de cada recurso. Ver
[`infra/nginx/`](infra/nginx/nginx.conf) para instrucciones.

### 3. Levantar el frontend

```bash
cd frontend

npm install
npm run dev
```

Abrir <http://localhost:5173>.

**Para probar desde el celular** (misma red WiFi):

```bash
npm run dev -- --host
```

Vite muestra una URL de red (tipo `http://192.168.x.x:5173`) que podés abrir desde el navegador del celular.

---

## Variables de entorno

Copiá la plantilla y completá los valores:

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

El archivo `.env` está en `.gitignore` — nunca se sube al repositorio.

---

## Instalar como app (PWA)

El frontend es una PWA: se instala en el celular sin pasar por App Store ni Play Store.

- **Android (Chrome):** el navegador ofrece automáticamente "Instalar aplicación".
- **iOS (Safari):** botón Compartir → "Agregar a pantalla de inicio".
- **Escritorio (Chrome/Edge):** ícono de instalación en la barra de direcciones.

---

## Comandos útiles de Django

```bash
python manage.py makemigrations      # Crear migraciones tras cambiar modelos
python manage.py migrate             # Aplicar migraciones
python manage.py createsuperuser     # Crear usuario admin
python manage.py shell                # Consola interactiva con los modelos
python manage.py check                # Verificar problemas del proyecto
```

Panel de administración: <http://localhost:8001/admin>

---

## Stack

**Backend:** Django, Django REST Framework, PostgreSQL, Redis, RabbitMQ
**Agente IA:** LangGraph
**Frontend:** React, Vite, React Router, PWA (vite-plugin-pwa)
**Infraestructura:** Docker, GitHub Actions

---

## Equipo

- Emmanuel Castaño
- Juan José Álvarez
- Santiago Meneses

Profesor: Nicolás Ramírez Vélez
Universidad EAFIT — Escuela de Ciencias Aplicadas e Ingeniería
Medellín, Antioquia
