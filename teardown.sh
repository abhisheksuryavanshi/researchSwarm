#!/usr/bin/env bash
# Tear down local resources started by setup.sh: background Uvicorn, Vite (operator UI),
# Redis container, Docker Compose MySQL (and optionally Compose volumes / Redis removal).
# Does not remove .venv, .env, or Python deps.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

REDIS_CONTAINER_NAME="${REDIS_CONTAINER_NAME:-researchswarm-redis}"
REMOVE_VOLUMES=0
REMOVE_REDIS_CONTAINER=0

ok() { echo "✅ $*"; }
warn() { echo "⚠️  $*"; }

usage() {
  echo "Tear down local resources started by setup.sh (Uvicorn, Vite, Redis, Compose MySQL)."
  echo ""
  echo "Usage: $0 [options]"
  echo "  --volumes, -v     docker compose down -v (wipes MySQL named volume)"
  echo "  --remove-redis    docker rm -f the Redis container (setup.sh will recreate)"
  echo "  -h, --help        Show this help"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --volumes|-v)
      REMOVE_VOLUMES=1
      shift
      ;;
    --remove-redis)
      REMOVE_REDIS_CONTAINER=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      warn "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

echo "== researchSwarm teardown =="

# --- Uvicorn started by setup.sh (PID file) ---
PID_FILE="${ROOT}/logs/uvicorn.pid"
LEGACY_PID="${ROOT}/.uvicorn-setup.pid"
if [[ -f "$PID_FILE" ]]; then
  :
elif [[ -f "$LEGACY_PID" ]]; then
  PID_FILE="$LEGACY_PID"
fi
if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    kill -TERM "$pid" 2>/dev/null || true
    sleep 0.5
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL "$pid" 2>/dev/null || true
    fi
    ok "Stopped Uvicorn (PID $pid from $PID_FILE)"
  else
    warn "Stale or empty PID file (PID was: ${pid:-empty}) — $PID_FILE"
  fi
  rm -f "$PID_FILE"
  rm -f "$LEGACY_PID"
else
  warn "No logs/uvicorn.pid (or legacy .uvicorn-setup.pid) — if Uvicorn is running, stop it manually"
fi

# --- Vite (operator web UI) started by setup.sh ---
VITE_PID_FILE="${ROOT}/logs/vite.pid"
if [[ -f "$VITE_PID_FILE" ]]; then
  vpid="$(cat "$VITE_PID_FILE" 2>/dev/null || true)"
  if [[ -n "${vpid:-}" ]] && kill -0 "$vpid" 2>/dev/null; then
    kill -TERM "$vpid" 2>/dev/null || true
    sleep 0.5
    if kill -0 "$vpid" 2>/dev/null; then
      kill -KILL "$vpid" 2>/dev/null || true
    fi
    ok "Stopped Vite (PID $vpid from $VITE_PID_FILE)"
  else
    warn "Stale or empty Vite PID file (PID was: ${vpid:-empty}) — $VITE_PID_FILE"
  fi
  rm -f "$VITE_PID_FILE"
else
  warn "No logs/vite.pid — if the operator UI dev server is running, stop it manually"
fi

# --- Redis (standalone container from setup.sh) ---
if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$REDIS_CONTAINER_NAME"; then
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$REDIS_CONTAINER_NAME"; then
    docker stop "$REDIS_CONTAINER_NAME" >/dev/null
    ok "Stopped Redis container $REDIS_CONTAINER_NAME"
  else
    ok "Redis container $REDIS_CONTAINER_NAME already stopped"
  fi
  if [[ "$REMOVE_REDIS_CONTAINER" -eq 1 ]]; then
    docker rm -f "$REDIS_CONTAINER_NAME" >/dev/null 2>&1 || true
    ok "Removed Redis container $REDIS_CONTAINER_NAME"
  fi
else
  warn "No Redis container named $REDIS_CONTAINER_NAME"
fi

# --- MySQL via Compose ---
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  warn "docker compose not available; skipped MySQL teardown"
else
  if [[ "$REMOVE_VOLUMES" -eq 1 ]]; then
    docker compose down -v
    ok "docker compose down -v (MySQL volume removed)"
  else
    docker compose down
    ok "docker compose down (MySQL container stopped; volume kept)"
  fi
fi

echo ""
ok "Teardown finished. .venv, .env, and logs are unchanged."
if [[ "$REMOVE_VOLUMES" -ne 1 ]]; then
  echo "    To wipe DB data next time: $0 --volumes"
fi
