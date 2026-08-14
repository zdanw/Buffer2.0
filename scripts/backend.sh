#!/usr/bin/env bash
# Control local backend (uvicorn on :8080)
#
# Usage:
#   ./scripts/backend.sh start|stop|status|restart

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Git Bash on Windows: use PowerShell (cmd.exe start breaks the terminal).
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    if command -v powershell.exe >/dev/null 2>&1; then
      exec powershell.exe -NoProfile -File "$SCRIPT_DIR/backend.ps1" "${1:-}"
    fi
    ;;
esac

# shellcheck disable=SC1091
source "$SCRIPT_DIR/dev-common.sh"

PORT=8080
LOG_FILE="$DEV_STATE_DIR/backend.log"
PID_FILE="$DEV_STATE_DIR/backend.pid"

usage() {
  cat <<EOF
Usage: $(basename "$0") <start|stop|status|restart>

Examples:
  $(basename "$0") start
  $(basename "$0") stop
  $(basename "$0") status
EOF
}

status() {
  local pids code
  pids="$(dev_port_pids "$PORT" | tr '\n' ' ')"
  code="$(dev_http_code "http://localhost:${PORT}/health")"
  if [ "$code" = "200" ]; then
    echo "running (port $PORT, health OK${pids:+, pid(s) $pids})"
    return 0
  fi
  if [ -n "$pids" ]; then
    echo "starting or unhealthy (port $PORT, pid(s) $pids)"
    return 1
  fi
  echo "stopped"
  return 1
}

activate_venv() {
  if [ ! -d "$DEV_BACKEND_DIR/.venv" ]; then
    echo "error: venv not found at $DEV_BACKEND_DIR/.venv"
    echo "Create it with:"
    echo "  cd backend && python -m venv .venv && source .venv/Scripts/activate && pip install -r requirements.txt"
    exit 1
  fi
  if dev_is_windows; then
    # shellcheck disable=SC1091
    source "$DEV_BACKEND_DIR/.venv/Scripts/activate"
  else
    # shellcheck disable=SC1091
    source "$DEV_BACKEND_DIR/.venv/bin/activate"
  fi
}

start() {
  if status >/dev/null 2>&1; then
    echo "backend: $(status)"
    echo "Already running. Use: $(basename "$0") restart"
    return 0
  fi

  if [ ! -f "$DEV_BACKEND_DIR/.env" ]; then
    if [ -f "$DEV_BACKEND_DIR/.env.example" ]; then
      cp "$DEV_BACKEND_DIR/.env.example" "$DEV_BACKEND_DIR/.env"
      echo "Created backend/.env from .env.example"
    else
      echo "error: missing backend/.env"
      exit 1
    fi
  fi

  echo "backend: starting..."
  activate_venv
  (
    cd "$DEV_BACKEND_DIR"
    nohup uvicorn bebcare.main:app --host 0.0.0.0 --port "$PORT" --reload \
      >>"$LOG_FILE" 2>&1 &
  )

  for i in $(seq 1 30); do
    if dev_port_listening "$PORT"; then
      if [ "$(dev_http_code "http://localhost:${PORT}/health")" = "200" ]; then
        echo "backend: started -> http://localhost:${PORT} (log: .dev/backend.log)"
        return 0
      fi
    fi
    sleep 1
  done

  echo "backend: launched but health check failed. See .dev/backend.log"
  tail -n 20 "$LOG_FILE" || true
  exit 1
}

stop() {
  if dev_stop_port "$PORT"; then
    rm -f "$PID_FILE"
    echo "backend: stopped"
  else
    rm -f "$PID_FILE"
    echo "backend: not running"
  fi
}

ACTION="${1:-}"
case "$ACTION" in
  start) start ;;
  stop) stop ;;
  status) echo "backend: $(status)" ;;
  restart) stop; start ;;
  *) usage; exit 1 ;;
esac
