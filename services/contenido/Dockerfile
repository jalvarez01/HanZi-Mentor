# Imagen del servicio Django `contenido` (el lado "legacy" del Strangler Pattern).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Las dependencias van antes que el código para aprovechar la caché de capas.
COPY requirements.txt requirements-docker.txt ./
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY . .

# El repo también se clona en Windows (autocrlf): se normalizan los finales
# de línea del script para que /bin/sh pueda ejecutarlo.
RUN sed -i 's/\r$//' docker-entrypoint.sh \
    && useradd --create-home appuser
USER appuser

EXPOSE 8002

ENTRYPOINT ["sh", "docker-entrypoint.sh"]
# --access-logfile - manda cada petición a stdout (docker compose logs contenido).
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8002", "--access-logfile", "-", "config.wsgi:application"]
