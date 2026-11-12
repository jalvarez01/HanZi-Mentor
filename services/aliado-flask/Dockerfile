# Imagen del microservicio que consume al equipo aliado (VaultDrop) vía Adapter.
# Es independiente del monolito: solo copia services/aliado-flask.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=aliado-flask

WORKDIR /app

# Las dependencias van antes que el código para aprovechar la caché de capas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Compila las traducciones (.po a .mo): los .mo no se suben al repo, así la
# imagen siempre tiene los mensajes al día.
RUN pybabel compile -d translations

RUN useradd --create-home appuser
USER appuser

EXPOSE 5000

# Igual que en services/flask-base. docker-compose.yml define el suyo y tiene prioridad.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=3)"

# Un solo proceso con 4 hilos: el respaldo (último catálogo de VaultDrop) vive
# en memoria y así lo comparten todas las peticiones. Con varios procesos,
# uno que nunca alcanzó a pedir el catálogo respondería 503 aunque otro sí lo
# tenga. --access-logfile - manda cada petición a stdout
# (docker compose logs flask_aliado).
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:5000", "--access-logfile", "-", "app:create_app()"]
