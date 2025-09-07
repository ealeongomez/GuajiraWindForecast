#!/usr/bin/env bash
# ==============================================================================
# Script: download_last_10y.sh
# Desc:   Dispara descargas por año (10 años hacia atrás) contra tu API /download/bulk.
#         Puede correr en modo "daemon" y ejecutar SOLO al minuto 1 de cada hora.
# Uso:
#   # una sola ejecución inmediata
#   ./download_last_10y.sh http://localhost:8000 --start-hour 0 --end-hour 23
#
#   # eliminar CSV antes de descargar (una sola vez)
#   ./download_last_10y.sh http://localhost:8000 --clean --data-dir data/raw
#
#   # daemon: ejecutar SIEMPRE al minuto 1 de cada hora
#   ./download_last_10y.sh http://localhost:8000 --daemon-min1 --start-hour 0 --end-hour 23
#
#   # daemon + limpiar antes de cada ciclo
#   ./download_last_10y.sh http://localhost:8000 --daemon-min1 --clean-each --data-dir data/raw
# ==============================================================================

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"; shift || true

# ---- opciones
CLEAN="false"         # limpiar una sola vez antes de descargar
CLEAN_EACH="false"    # limpiar ANTES de cada ciclo (solo si --daemon-min1)
ASSUME_YES="false"
DATA_DIR="${DATA_DIR:-data/raw}"    # carpeta local donde la API guarda CSV (si es la misma máquina)
START_HOUR="${START_HOUR:-0}"
END_HOUR="${END_HOUR:-23}"
WIND_ONLY="${WIND_ONLY:-false}"
SLEEP_BETWEEN="${SLEEP_BETWEEN:-0.5}"
DAEMON_MIN1="false"
LOCK_DIR="${LOCK_DIR:-/tmp/download_last_10y.lock}"
LOG_FILE="${LOG_FILE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean) CLEAN="true"; shift ;;
    --clean-each) CLEAN_EACH="true"; shift ;;
    --yes|-y) ASSUME_YES="true"; shift ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --start-hour) START_HOUR="$2"; shift 2 ;;
    --end-hour) END_HOUR="$2"; shift 2 ;;
    --wind-only) WIND_ONLY="true"; shift ;;
    --sleep) SLEEP_BETWEEN="$2"; shift 2 ;;
    --daemon-min1) DAEMON_MIN1="true"; shift ;;
    --log) LOG_FILE="$2"; shift 2 ;;
    -h|--help)
      echo "Uso: $(basename "$0") [BASE_URL] [--clean] [--clean-each] [--yes] [--data-dir PATH] [--start-hour N] [--end-hour N] [--wind-only] [--sleep S] [--daemon-min1] [--log FILE]"
      exit 0
      ;;
    *) echo "Opción desconocida: $1"; exit 1 ;;
  esac
done

log() {
  local ts; ts="$(date '+%Y-%m-%d %H:%M:%S')"
  if [[ -n "$LOG_FILE" ]]; then
    echo "[$ts] $*" | tee -a "$LOG_FILE"
  else
    echo "[$ts] $*"
  fi
}

# ---- helpers de fecha (macOS y Linux)
date_yesterday() {
  date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d
}
date_minus_10y_same_day() {
  local ref="$1"
  local y m d
  y="${ref:0:4}"; m="${ref:5:2}"; d="${ref:8:2}"
  (date -d "${y}-${m}-${d} -10 years" +%Y-%m-%d 2>/dev/null) \
    || (date -j -v-10y -f "%Y-%m-%d" "${y}-${m}-${d}" "+%Y-%m-%d" 2>/dev/null) \
    || echo "$((y-10))-${m}-${d}"
}

yesterday="$(date_yesterday)"
ten_years_ago="$(date_minus_10y_same_day "$yesterday")"
start_year="${ten_years_ago:0:4}"
end_year="${yesterday:0:4}"

# ---- limpieza local
clean_csvs() {
  log "⚠️  Se borrarán archivos CSV en: $DATA_DIR"
  mkdir -p "$DATA_DIR"
  if [[ "$ASSUME_YES" != "true" ]]; then
    read -r -p "¿Confirmas borrar *.csv en $DATA_DIR? [y/N] " resp
    [[ "${resp,,}" == "y" || "${resp,,}" == "yes" ]] || { log "Cancelado."; return 1; }
  fi
  find "$DATA_DIR" -maxdepth 1 -type f -name "*.csv" -print -delete || true
  log "🧹 Limpieza completada en $DATA_DIR."
}

# ---- POST /download/bulk a tu API
post_bulk() {
  local start_date="$1"
  local end_date="$2"
  curl -s -X POST "${BASE_URL%/}/download/bulk" \
    -H "Content-Type: application/json" \
    -d "{\"start_date\":\"$start_date\",\"end_date\":\"$end_date\",\"start_hour\":$START_HOUR,\"end_hour\":$END_HOUR,\"wind_only\":$WIND_ONLY,\"cities\":null}"
}

run_once() {
  log "🚀 Descarga 10y atrás usando ${BASE_URL}"
  log "    Horario: ${START_HOUR}:00 - ${END_HOUR}:00  | wind_only=${WIND_ONLY}"
  log "    DATA_DIR local: ${DATA_DIR}"
  log "    Rango total: $ten_years_ago → $yesterday"
  log "    ==========================================="

  # Limpieza inicial si se pidió
  if [[ "$CLEAN" == "true" ]]; then
    clean_csvs || true
  fi

  # Primer bloque parcial si aplica
  if [[ "$start_year" != "$end_year" ]]; then
    local first_end="${start_year}-12-31"
    log "📦 Bloque: $ten_years_ago → $first_end"
    post_bulk "$ten_years_ago" "$first_end"
    echo
    sleep "$SLEEP_BETWEEN"
  fi

  # Años completos intermedios
  local year=$((start_year+1))
  while [[ $year -lt $end_year ]]; do
    log "📦 Bloque: $year-01-01 → $year-12-31"
    post_bulk "$year-01-01" "$year-12-31"
    echo
    sleep "$SLEEP_BETWEEN"
    year=$((year+1))
  done

  # Último bloque del año actual
  log "📦 Bloque: $end_year-01-01 → $yesterday"
  post_bulk "$end_year-01-01" "$yesterday"
  echo

  # Listado final de archivos reportados por la API
  log "📁 Archivos reportados por la API (/files):"
  curl -s "${BASE_URL%/}/files"
  echo
}

# ---- scheduler: dormir hasta el minuto 1
sleep_until_minute1() {
  local m s mm ss sleep_s
  m="$(date +%M)"; s="$(date +%S)"
  # Quitar ceros a la izquierda para aritmética
  mm=$((10#$m)); ss=$((10#$s))
  if (( mm < 1 )); then
    sleep_s=$(( (1 - mm)*60 - ss ))
  else
    sleep_s=$(( ((60 - mm) + 1)*60 - ss ))
  fi
  (( sleep_s < 0 )) && sleep_s=0
  log "⏳ Durmiendo ${sleep_s}s hasta el próximo HH:01..."
  sleep "$sleep_s"
}

# ---- lock para evitar ejecuciones simultáneas
acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    trap 'rm -rf "$LOCK_DIR"' EXIT
    return 0
  else
    log "🔒 Ya hay otra instancia corriendo (lock: $LOCK_DIR). Saliendo."
    exit 0
  fi
}

# ---- main
if [[ "$DAEMON_MIN1" == "true" ]]; then
  acquire_lock
  log "🟢 Modo daemon: se ejecutará SOLO al minuto 1 de cada hora."
  while true; do
    sleep_until_minute1
    # limpieza en cada ciclo si se pidió
    if [[ "$CLEAN_EACH" == "true" ]]; then
      CLEAN="false"   # evita doble limpieza si también se pasó --clean
      clean_csvs || true
    fi
    run_once
  done
else
  run_once
fi
