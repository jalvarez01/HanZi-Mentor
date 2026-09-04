#!/usr/bin/env bash
# Levanta los 3 backends Django (usuarios, contenido, agente-tutor) con un solo comando.
#
# Uso:
#   ./infra/scripts/levantar_backends.sh
#   ./infra/scripts/levantar_backends.sh --migrate   # corre "migrate" antes de levantar cada uno
#
# Ctrl+C detiene los tres procesos.

set -euo pipefail
set -m  # cada backend corre en su propio process group, para poder matar reloader + hijos juntos

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="$ROOT_DIR/infra/scripts/.logs"
mkdir -p "$LOG_DIR"

RUN_MIGRATE=false
if [[ "${1:-}" == "--migrate" ]]; then
  RUN_MIGRATE=true
fi

# nombre:puerto
SERVICIOS=(
  "usuarios:8001"
  "contenido:8002"
  "agente-tutor:8003"
)

PIDS=()

CLEANED_UP=false
cleanup() {
  $CLEANED_UP && return
  CLEANED_UP=true
  echo ""
  echo "Deteniendo backends..."
  for pid in "${PIDS[@]}"; do
    # manage.py runserver lanza un subproceso (el auto-reloader); matamos
    # todo el process group, no solo el pid del padre.
    kill -TERM "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "Listo."
}
trap cleanup EXIT INT TERM

for entry in "${SERVICIOS[@]}"; do
  nombre="${entry%%:*}"
  puerto="${entry##*:}"
  dir="$ROOT_DIR/services/$nombre"
  venv="$dir/venv"

  if [[ ! -d "$dir" ]]; then
    echo "AVISO: no existe $dir, se omite."
    continue
  fi

  if [[ ! -d "$venv" ]]; then
    echo "AVISO: $nombre no tiene venv. Creándolo e instalando dependencias..."
    python3 -m venv "$venv"
    "$venv/bin/pip" install -q -r "$dir/requirements.txt"
  fi

  if $RUN_MIGRATE; then
    echo "Migrando $nombre..."
    (cd "$dir" && "$venv/bin/python" manage.py migrate) || {
      echo "ERROR: falló migrate en $nombre"; exit 1;
    }
  fi

  # Si quedó un proceso colgado de una corrida anterior ocupando el puerto
  # (p. ej. el script se cortó sin limpiar bien), lo liberamos antes de levantar.
  ocupante="$(lsof -tiTCP:"$puerto" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$ocupante" ]]; then
    echo "AVISO: puerto $puerto ocupado (pid $ocupante), liberando..."
    kill -9 $ocupante 2>/dev/null || true
    sleep 0.5
  fi

  echo "Levantando $nombre en puerto $puerto (log: infra/scripts/.logs/$nombre.log)"
  # 0.0.0.0 en vez de solo el puerto: así responde también por la IP de LAN
  # (necesario si el frontend usa VITE_*_URL con una IP en vez de localhost).
  (cd "$dir" && "$venv/bin/python" manage.py runserver "0.0.0.0:$puerto") \
    > "$LOG_DIR/$nombre.log" 2>&1 &
  PIDS+=("$!")
done

echo ""
echo "Backends corriendo:"
echo "  usuarios      -> http://localhost:8001"
echo "  contenido     -> http://localhost:8002"
echo "  agente-tutor  -> http://localhost:8003"
echo ""
echo "Logs en infra/scripts/.logs/*.log. Ctrl+C para detener todo."

wait
