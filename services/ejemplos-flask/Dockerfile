# Imagen del microservicio de oraciones de ejemplo (API de terceros vía Adapter).
# Es independiente del monolito: solo copia services/ejemplos-flask.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=ejemplos-flask

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

# --access-logfile - manda cada petición a stdout (docker compose logs flask_ejemplos).
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "--access-logfile", "-", "app:create_app()"]
