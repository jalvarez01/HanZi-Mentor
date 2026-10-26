# Imagen del microservicio de catálogo: caracteres, trazos y lecciones (T13).
# Es independiente del monolito: solo copia services/catalogo-flask.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=catalogo-flask \
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

# Usuario sin privilegios. Es dueño de /app para poder crear la base SQLite
# local cuando no se define DATABASE_URL. El script de arranque se normaliza
# por si el repo se clonó en Windows (autocrlf).
RUN sed -i 's/\r$//' docker-entrypoint.sh \
    && useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 5000

# La imagen slim no trae curl: se consulta /health con la stdlib.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT', '5000'), timeout=3)"

# Carga el dataset de /datos si la base está vacía y después ejecuta CMD.
ENTRYPOINT ["sh", "docker-entrypoint.sh"]

# Forma shell para expandir PORT y GUNICORN_WORKERS; exec deja a gunicorn como PID 1.
CMD ["sh", "-c", "exec gunicorn -w ${GUNICORN_WORKERS} -b 0.0.0.0:${PORT} --access-logfile - 'app:create_app()'"]
