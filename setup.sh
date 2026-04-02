#!/usr/bin/env bash
# Local setup for researchSwarm: checks deps, env file, installs packages,
# starts MySQL (Docker Compose) and Redis (named container), migrates, seeds.
# Idempotent: safe to run multiple times.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

REDIS_CONTAINER_NAME="${REDIS_CONTAINER_NAME:-researchswarm-redis}"

ok() { echo "✅ $*"; }
fail() { echo "❌ $*"; exit 1; }
warn() { echo "⚠️  $*"; }

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required command not found: $1"
  fi
}

echo "== researchSwarm setup =="

need_cmd docker
if ! docker compose version >/dev/null 2>&1; then
  fail "Docker Compose V2 required (docker compose). Install Docker Desktop or docker-compose-plugin."
fi
need_cmd python3
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
  || fail "Python 3.9+ required (found: $(python3 -V 2>&1))"

ok "Prerequisite commands found (git, docker compose, python3 >= 3.9)"

# --- .env ---
if [[ -f .env ]]; then
  ok ".env already exists (left unchanged)"
else
  if [[ ! -f .env.example ]]; then
    fail ".env.example is missing; cannot create .env"
  fi
  cp .env.example .env
  ok "Created .env from .env.example"
fi

# --- Python dependencies ---
if command -v uv >/dev/null 2>&1; then
  uv sync --extra dev
  ok "Dependencies installed with uv sync --extra dev"
  RUN=(uv run)
else
  warn "uv not found; using venv + pip (install uv for lockfile reproducibility)"
  if [[ ! -d .venv ]]; then
    python3 -m venv .venv
    ok "Created .venv"
  else
    ok ".venv already exists"
  fi
  # shellcheck disable=SC1091
  ./.venv/bin/pip install -U pip
  ./.venv/bin/pip install -e ".[dev]"
  ok "Dependencies installed with pip install -e \".[dev]\""
  RUN=(./.venv/bin/python -m)
fi

# --- MySQL via Compose ---
docker compose up -d mysql
ok "Docker Compose service mysql is up (docker compose up -d mysql)"

echo "Waiting for MySQL to accept connections..."
mysql_ready=0
for _ in $(seq 1 36); do
  if docker compose exec -T mysql mysqladmin ping -h localhost -uroot -proot --silent >/dev/null 2>&1; then
    mysql_ready=1
    break
  fi
  sleep 2
done
if [[ "$mysql_ready" -ne 1 ]]; then
  fail "MySQL did not become ready in time. Try: docker compose logs mysql"
fi
ok "MySQL is reachable"

# --- Redis (not in docker-compose.yml) ---
if docker ps -a --format '{{.Names}}' | grep -qx "$REDIS_CONTAINER_NAME"; then
  docker start "$REDIS_CONTAINER_NAME" >/dev/null 2>&1 || true
  ok "Redis container $REDIS_CONTAINER_NAME present and started"
else
  docker run -d --name "$REDIS_CONTAINER_NAME" -p 6379:6379 redis:7-alpine >/dev/null
  ok "Created and started Redis container $REDIS_CONTAINER_NAME (redis:7-alpine on :6379)"
fi

# --- Migrations (uses sqlalchemy.url in alembic.ini) ---
# Lenient for local reruns: ignores MySQL "already exists" (1050) / duplicate column/key (1060/1061).
if [[ "${RUN[0]}" == "uv" ]]; then
  uv run python "$ROOT/scripts/alembic_upgrade_lenient.py"
else
  ./.venv/bin/python "$ROOT/scripts/alembic_upgrade_lenient.py"
fi
ok "Alembic upgrade step finished (lenient mode for duplicate objects — see script if warnings appeared)"

# --- Seed ---
if [[ "${RUN[0]}" == "uv" ]]; then
  uv run python -m registry.seed
else
  ./.venv/bin/python -m registry.seed
fi
ok "Registry seed completed (python -m registry.seed)"

# --- Optional: start API if nothing listens on 8000 ---
if command -v curl >/dev/null 2>&1; then
  if curl -sf -o /dev/null "http://127.0.0.1:8000/openapi.json" 2>/dev/null; then
    ok "API already responding at http://127.0.0.1:8000 — not starting another Uvicorn"
  else
    LOG_DIR="${ROOT}/logs"
    mkdir -p "$LOG_DIR"
    LOG_FILE="${LOG_DIR}/uvicorn.log"
    PID_FILE="${LOG_DIR}/uvicorn.pid"
    if [[ "${RUN[0]}" == "uv" ]]; then
      nohup uv run uvicorn registry.app:app --host 0.0.0.0 --port 8000 --reload >>"$LOG_FILE" 2>&1 &
    else
      nohup ./.venv/bin/uvicorn registry.app:app --host 0.0.0.0 --port 8000 --reload >>"$LOG_FILE" 2>&1 &
    fi
    echo $! >"$PID_FILE"
    ok "Started Uvicorn in background (PID $(cat "$PID_FILE"), log $LOG_FILE)"
    warn "Stop with: kill \$(cat $PID_FILE)  # when you are done"
  fi
else
  warn "curl not installed; skipping listen check. Start the app manually:"
  if [[ "${RUN[0]}" == "uv" ]]; then
    echo "    uv run uvicorn registry.app:app --host 0.0.0.0 --port 8000 --reload"
  else
    echo "    ./.venv/bin/uvicorn registry.app:app --host 0.0.0.0 --port 8000 --reload"
  fi
fi

echo ""
ok "Setup finished. Open http://127.0.0.1:8000/docs when Uvicorn is running."
echo "⚠️  TODO: Set GOOGLE_API_KEY in .env for live Gemini calls."
echo "⚠️  TODO: Add CONVERSATION_* vars to .env if you rely on session APIs; see SETUP.md."
