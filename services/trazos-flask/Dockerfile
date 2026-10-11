# Imagen del microservicio de validación de trazos (Strangler Pattern, taller 02).
# Es independiente del monolito: solo copia services/trazos-flask.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Las dependencias van antes que el código para aprovechar la caché de capas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home appuser
USER appuser

EXPOSE 5000

# --access-logfile - manda cada petición a stdout (docker compose logs flask_trazos).
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "--access-logfile", "-", "app:create_app()"]
