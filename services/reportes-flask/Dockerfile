# Imagen del microservicio de reportes asíncronos (T18 y T19).
# Es independiente del monolito: solo copia services/reportes-flask.
# La usan dos servicios del compose: flask_reportes (gunicorn, el CMD de
# abajo) y worker (celery, que reemplaza CMD y el healthcheck).
# No tiene base de datos: no usa script de arranque.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=reportes-flask \
    PORT=5000 \
    GUNICORN_WORKERS=2

WORKDIR /app

# Las dependencias van antes que el código para aprovechar la caché de capas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Compila las traducciones (.po a .mo): los .mo no se suben al repo, así la
# imagen siempre tiene los mensajes al día.
RUN pybabel compile -d translations

# Usuario sin privilegios: Celery advierte si el worker corre como root.
RUN useradd --create-home appuser
USER appuser

EXPOSE 5000

# La imagen slim no trae curl: se consulta /health con la stdlib. /health
# responde 503 si Redis no contesta.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT', '5000'), timeout=3)"

# Forma shell para expandir PORT y GUNICORN_WORKERS; exec deja a gunicorn como PID 1.
CMD ["sh", "-c", "exec gunicorn -w ${GUNICORN_WORKERS} -b 0.0.0.0:${PORT} --access-logfile - 'app:create_app()'"]
