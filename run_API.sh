#!/usr/bin/env bash
# ==============================================================================
# Script: run_API.sh
# Levanta FastAPI (api.dataAPI:app) ubicado en src/api/dataAPI.py
# - Activa .venv si existe
# - Usa --app-dir ./src (raíz de paquetes)
# - --kill para liberar el puerto si está ocupado
# ==============================================================================

set -euo pipefail

# ▶️ Activa venv si existe
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# ⚙️ Defaults (puedes sobreescribir con variables de entorno)
APP_MODULE="${APP_MODULE:-api.dataAPI:app}"   # src/api/dataAPI.py  -> paquete: api.dataAPI
APP_DIR="${APP_DIR:-./src}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
DATA_DIR="${DATA_DIR:-data/raw}"
STATE_DIR="${STATE_DIR:-data/state}"
RELOAD="${RELOAD:-true}"
KILL="false"

# 🔤 Flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--port) PORT="$2"; shift 2 ;;
    -H|--host) HOST="$2"; shift 2 ;;
    --kill)    KILL="true"; shift ;;
    --no-reload) RELOAD="false"; shift ;;
    -h|--help)
      echo "Uso: $0 [-p|--port N] [--kill] [--no-reload] [-H|--host HOST]"
      exit 0 ;;
    *) echo "Opción no reconocida: $1"; exit 1 ;;
  esac
done

# 📂 Directorios
mkdir -p "$DATA_DIR" "$STATE_DIR"
export DATA_DIR STATE_DIR  # la API los leerá

# 🔎 Puerto en uso?
port_in_use() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$PORT" -sTCP:LISTEN -nP >/dev/null 2>&1
  else
    (echo >/dev/tcp/127.0.0.1/$PORT) >/dev/null 2>&1
  fi
}

if port_in_use; then
  echo "⚠️  Puerto $PORT ocupado."
  if [[ "$KILL" == "true" ]] && command -v lsof >/dev/null 2>&1; then
    PIDS=$(lsof -t -iTCP:"$PORT" -sTCP:LISTEN -nP | tr '\n' ' ')
    echo "🛑 Matando procesos: $PIDS"
    kill -INT $PIDS 2>/dev/null || true; sleep 1
    kill -TERM $PIDS 2>/dev/null || true; sleep 1
    kill -KILL $PIDS 2>/dev/null || true; sleep 1
  else
    echo "❌ Usa --kill o elige otro puerto con -p"
    exit 1
  fi
fi

# 🚀 Lanzar Uvicorn
echo "🚀 Iniciando API:"
echo "   - APP_MODULE : $APP_MODULE"
echo "   - APP_DIR    : $APP_DIR"
echo "   - HOST       : $HOST"
echo "   - PORT       : $PORT"
echo "   - DATA_DIR   : $DATA_DIR"
echo "   - STATE_DIR  : $STATE_DIR"
echo "   - RELOAD     : $RELOAD"

UVICORN_ARGS=( "$APP_MODULE" --host "$HOST" --port "$PORT" --app-dir "$APP_DIR" )
[[ "$RELOAD" == "true" ]] && UVICORN_ARGS+=( --reload )

exec uvicorn "${UVICORN_ARGS[@]}"
