# Imagen del microservicio de progreso y repaso espaciado (T11).
# Es independiente del monolito: solo copia services/progreso-flask.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=progreso-flask \
    PORT=5000 \
    GUNICORN_WORKERS=2

WORKDIR /app

# Las dependencias van antes que el código para aprovechar la caché de capas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usuario sin privilegios. Es dueño de /app para poder crear la base SQLite
# local cuando no se define DATABASE_URL.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 5000

# La imagen slim no trae curl: se consulta /health con la stdlib.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT', '5000'), timeout=3)"

# Forma shell para expandir PORT y GUNICORN_WORKERS; exec deja a gunicorn como PID 1.
CMD ["sh", "-c", "exec gunicorn -w ${GUNICORN_WORKERS} -b 0.0.0.0:${PORT} --access-logfile - 'app:create_app()'"]
