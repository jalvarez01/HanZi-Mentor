# Imagen del servicio Django `agente-tutor` (sesiones, respuestas y progreso).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Las dependencias van antes que el código para aprovechar la caché de capas.
COPY requirements.txt requirements-docker.txt ./
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY . .

# settings.py fija la base en /app/db.sqlite3. Sin tocar settings.py, ese
# archivo es un enlace a /app/data/db.sqlite3, donde docker-compose.yml monta
# el volumen agente_tutor_db: la base sobrevive a recrear el contenedor.
# SQLite resuelve el enlace, así que el -journal también queda en /app/data.
# El repo también se clona en Windows (autocrlf): se normalizan los finales
# de línea del script para que /bin/sh pueda ejecutarlo.
RUN sed -i 's/\r$//' docker-entrypoint.sh \
    && useradd --create-home appuser \
    && mkdir -p /app/data \
    && ln -sf /app/data/db.sqlite3 /app/db.sqlite3 \
    && chown -R appuser:appuser /app/data
USER appuser

EXPOSE 8003

ENTRYPOINT ["sh", "docker-entrypoint.sh"]
# --access-logfile - manda cada petición a stdout (docker compose logs agente_tutor).
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8003", "--access-logfile", "-", "config.wsgi:application"]
